import asyncio
import csv
import hashlib
import io
import json
import logging
import re
import shutil
import sqlite3
import tempfile
import zipfile
from contextlib import asynccontextmanager
from datetime import date, datetime
from pathlib import Path
from typing import List, Literal
from uuid import uuid4

from fastapi import FastAPI, File, Form, HTTPException, UploadFile, Request
from fastapi.responses import FileResponse, JSONResponse, Response
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field
from scanner.queue.background_scanner import QueueStore, ScannerQueue
from scanner.io.session_store import SessionError
from scanner.io.zip_import import prepare_archive, ImportError as BatchImportError
from scanner.reading.sample_dates import normalize_sample_date, sampled_date_issue
from scanner.io.session_cleanup import empty_uploads
from access_control import check_access
from grok_assistant import AssistantRequest, AssistantService, FIELDS
from automatic_capture import AutomaticCapture, make_router as make_capture_router

BASE = Path(__file__).resolve().parent
UPLOADS = BASE / "uploads"
UPLOADS.mkdir(exist_ok=True)
STORE = QueueStore(BASE / "scanner.sqlite3")
QUEUE = ScannerQueue(STORE, BASE)
ASSISTANT = AssistantService(STORE)
BOOT_ID = uuid4().hex

@asynccontextmanager
async def lifespan(app):
    removed = empty_uploads(UPLOADS)
    STORE.close_after_upload_reset()
    logging.info("Cleared %s upload entries on startup", removed)
    QUEUE.start()
    assistant_maintenance = asyncio.create_task(ASSISTANT.maintenance())
    try:
        yield
    finally:
        assistant_maintenance.cancel()
        try:
            await assistant_maintenance
        except asyncio.CancelledError:
            pass
        QUEUE.stop()

app = FastAPI(lifespan=lifespan)
app.mount("/static", StaticFiles(directory=BASE / "static"), name="static")

@app.middleware("http")
async def clerk_access(request: Request, call_next):
    try:
        check_access(request)
        if request.method == "POST" and request.url.path.endswith("/assistant"):
            size = request.headers.get("content-length", "")
            if not size.isdigit() or int(size) > 16_384:
                raise HTTPException(413, "Assistant request is too large.")
    except HTTPException as error:
        return JSONResponse({"detail": error.detail}, status_code=error.status_code, headers=error.headers)
    return await call_next(request)
TYPES = {"image/jpeg": ".jpg", "image/png": ".png", "image/webp": ".webp"}
COLUMNS = [
    ("sample_id", "Sample ID"), ("date_sampled", "Date Sampled"),
    ("date_received", "Date Received"), ("machine", "Machine"),
    ("component", "Component"), ("serial_number", "Serial Number"),
    ("reference_lube", "Reference Lube"),
]

@app.exception_handler(SessionError)
async def session_error(request, error):
    return JSONResponse(status_code=400, content={"detail": str(error)})

@app.exception_handler(sqlite3.Error)
async def database_error(request, error):
    logging.error("Database error: %s", error)
    return JSONResponse(status_code=503, content={
        "detail": "Session storage unavailable. Check Pi storage and retry."
    })

def status(session_id):
    result = STORE.status(session_id)
    result["boot_id"] = BOOT_ID
    return result

def folder_for(record_id):
    if not re.fullmatch(r"[0-9a-f]{32}", record_id):
        raise HTTPException(404, "Sample not found.")
    folder = UPLOADS / record_id
    if not (folder / "sample.json").is_file():
        raise HTTPException(404, "Sample not found.")
    return folder

def member_folder(record_id):
    membership = STORE.sample(record_id)
    if not membership or not membership.get("session_id"):
        raise HTTPException(404, "Sample not found.")
    return folder_for(record_id), membership

def valid_received(value):
    try:
        if not re.fullmatch(r"\d{4}-\d{2}-\d{2}", value):
            return False
        date.fromisoformat(value)
        return True
    except ValueError:
        return False

AUTO_CAPTURE = AutomaticCapture(STORE, UPLOADS)
app.include_router(make_capture_router(AUTO_CAPTURE, valid_received))

class NewSession(BaseModel):
    name: str = Field(default="", max_length=120)

class Fields(BaseModel):
    sample_id: str = Field(default="", max_length=200)
    date_sampled: str = Field(default="", max_length=200)
    date_received: str = Field(default="", max_length=10)
    machine: str = Field(default="", max_length=200)
    component: str = Field(default="", max_length=200)
    serial_number: str = Field(default="", max_length=200)
    reference_lube: str = Field(default="", max_length=200)

class Review(BaseModel):
    session_id: str
    label_type: Literal["small", "large", "unknown"]
    confirmed: bool = False
    fields: Fields
    expected_revision: int | None = None
    suggestion_request_id: str | None = Field(default=None, pattern=r"^[0-9a-f]{32}$")
    suggestion_field: str | None = None


class FinishExport(BaseModel):
    export_hash: str = Field(pattern=r'^[0-9a-f]{64}$')
    include_unreviewed: bool = False

@app.get("/")
def home():
    return FileResponse(BASE / "static" / "index.html",
                        headers={"Cache-Control": "no-store"})

@app.get("/app")
def app_info():
    import os
    enabled = os.getenv("ASSISTANT_ENABLED", "").lower() in {"1","true","yes"} and bool(os.getenv("XAI_API_KEY"))
    return {"boot_id": BOOT_ID, "assistant_available": enabled,
            "assistant_image_available": enabled and os.getenv("ASSISTANT_IMAGE_ENABLED", "").lower() in {"1","true","yes"}}

@app.post("/sessions")
def create_session(value: NewSession):
    session = STORE.create(value.name)
    return status(session["id"])


@app.get('/sessions')
def unfinished_sessions():
    return {'sessions':STORE.unfinished()}

@app.get("/sessions/{session_id}")
def session_status(session_id: str):
    return status(session_id)

@app.post("/sessions/{session_id}/retry/{record_id}")
def retry_sample(session_id: str, record_id: str):
    STORE.retry(session_id, record_id)
    return status(session_id)

@app.get("/sessions/{session_id}/csv")
def download_csv(session_id: str, include_unreviewed: bool = False):
    session = STORE.get(session_id)
    reviews = (
        STORE.reviews(session_id)
        if include_unreviewed
        else STORE.confirmed_reviews(session_id)
    )
    content = csv_bytes(reviews)
    return Response(content, media_type="text/csv",
        headers={
            "Content-Disposition": f'attachment; filename="samples-{session["id"]}.csv"',
            "Cache-Control": "no-store",
            "X-Export-Hash": hashlib.sha256(content).hexdigest(),
        })


def csv_bytes(reviews):
    output = io.StringIO(newline='')
    writer = csv.writer(output)
    writer.writerow([title for _, title in COLUMNS])
    for review in reviews:
        writer.writerow([csv_safe(review['fields'].get(key, '')) for key, _ in COLUMNS])
    return output.getvalue().encode('utf-8-sig')

def csv_safe(value):
    value = str(value or '')
    return "'" + value if value.lstrip().startswith(('=', '+', '-', '@')) or value.startswith(('\t', '\r', '\n')) else value


@app.post('/sessions/{session_id}/finish-export')
def finish_export(session_id: str, request: FinishExport):
    from scanner.io.session_cleanup import clear_uploads
    records = STORE.finish_for_export(session_id, request.export_hash,
                                     request.include_unreviewed, csv_bytes)
    try:
        count = clear_uploads(UPLOADS, records)
    except (OSError, ValueError):
        logging.exception('Could not clear finished session uploads')
        raise HTTPException(500, 'CSV is retained. Some photos could not be cleared; retry finishing this session.')
    return {'cleared_tubes':count}

@app.get("/samples/{record_id}/images/{number}")
def original_image(record_id: str, number: int):
    folder, _ = member_folder(record_id)
    sample = json.loads((folder / "sample.json").read_text(encoding="utf-8"))
    images = sample["images"]
    if not 1 <= number <= len(images):
        raise HTTPException(404, "Photo not found.")
    name = images[number - 1]["filename"]
    if not re.fullmatch(r"image_[1-8]\.(jpg|png|webp)", name):
        raise HTTPException(404, "Photo not found.")
    path = folder / name
    if not path.is_file():
        raise HTTPException(404, "Photo not found.")
    return FileResponse(path)

@app.get("/samples/{record_id}/evidence")
def combined_image(record_id: str):
    folder, membership = member_folder(record_id)
    review = membership["review"] if membership else None
    evidence = (review or {}).get("evidence") or {}
    run_id = evidence.get("run_id", "")
    if not re.fullmatch(r"[0-9a-f]{32}", run_id):
        raise HTTPException(404, "Combined image unavailable.")
    path = folder / "analysis" / run_id / "combined.jpg"
    if not path.is_file():
        raise HTTPException(404, "Combined image unavailable.")
    return FileResponse(path)


@app.get('/samples/{record_id}/fields/{field}')
def field_image(record_id: str, field: str):
    return FileResponse(field_path(record_id, field))

def field_path(record_id: str, field: str):
    if field not in {'sample_id', 'machine', 'date_sampled', 'component', 'serial_number', 'reference_lube'}:
        raise HTTPException(404, 'Field crop unavailable.')
    folder, membership = member_folder(record_id)
    review = (membership or {}).get('review') or {}
    evidence = review.get('evidence') or {}
    run = evidence.get('run_id', '')
    if not re.fullmatch(r'[0-9a-f]{32}', run):
        try:
            run = json.loads((folder/'ocr.json').read_text(encoding='utf-8')).get('run_id', '')
        except (OSError, ValueError):
            run = ''
    if not re.fullmatch(r'[0-9a-f]{32}', run):
        raise HTTPException(404, 'Field crop unavailable.')
    key = 'barcode' if field == 'sample_id' else field
    root = folder/'analysis'/run
    path = root/f'field_{key}.jpg'
    if not path.is_file():
        # Older records already have the individual text crops.
        number = evidence.get('sources', {}).get(key)
        if isinstance(number, int) and 1 <= number <= 8:
            path = root/f'photo_{number}_{key}.jpg'
    if not path.is_file():
        # The preview's selected-photo reference can be absent on older scans.
        # Look for this exact field in every photo in the same analysis run.
        path = next((root/f'photo_{number}_{key}.jpg' for number in range(1, 9)
                     if (root/f'photo_{number}_{key}.jpg').is_file()), path)
    if not path.is_file():
        raise HTTPException(404, 'Field crop unavailable. Check original photos.')
    return path

@app.post("/sessions/{session_id}/samples/{record_id}/assistant")
async def ask_assistant(session_id: str, record_id: str, request: AssistantRequest, connection: Request):
    crop = field_path(record_id, request.field) if request.action == "read" and request.field != "date_received" else None
    return await ASSISTANT.run(session_id, record_id, request, crop, connection.client.host if connection.client else "unknown")

@app.post("/samples/{record_id}/review")
def edit_review(record_id: str, request: Review):
    folder = folder_for(record_id)
    submitted_fields = request.fields.model_dump()
    fields = {
        key: value.strip()
        for key, value in submitted_fields.items()
    }
    fields["serial_number"] = fields["serial_number"].upper()
    fields['date_sampled'] = normalize_sample_date(fields['date_sampled'])
    if request.label_type == "small":
        fields["reference_lube"] = ""
        fields["component"] = fields["component"].upper()
    elif request.label_type == "large":
        fields["serial_number"] = ""

    if request.confirmed:
        if request.label_type == "unknown":
            raise HTTPException(400, "Choose Small or Large before confirming.")
        if not valid_received(fields["date_received"]):
            raise HTTPException(400, "Enter a valid Date Received.")
        issue=sampled_date_issue(fields['date_sampled'],fields['date_received'])
        if issue:
            raise HTTPException(400,issue)
        if request.label_type == "small" and fields["component"]:
            if not re.fullmatch(r"[1-6] (?:GS|NGS)", fields["component"]):
                raise HTTPException(400, "Component must look like 4 GS.")

    suggestion = None
    if request.suggestion_request_id:
        if not request.suggestion_field or request.suggestion_field not in FIELDS or request.expected_revision is None or request.confirmed:
            raise HTTPException(400, "Suggestion must be applied to an unconfirmed review.")
        suggestion = ASSISTANT.suggestion(request.session_id, record_id, request.suggestion_request_id,
            request.suggestion_field, request.expected_revision, submitted_fields[request.suggestion_field])
    review = STORE.edit(
        request.session_id, record_id, fields,
        request.label_type, request.confirmed, request.expected_revision, suggestion,
    )
    try:
        QUEUE.snapshot(folder / "review.json", review)
    except OSError:
        logging.exception("Database saved; review JSON snapshot failed")
    return {"review": review, "session": status(request.session_id)}

@app.post("/upload")
def upload(files: List[UploadFile] = File(...),
           session_id: str = Form(...), date_received: str = Form(...)):
    staging = destination = None
    completed = False
    try:
        STORE.require_active(session_id)
        if not valid_received(date_received):
            raise HTTPException(400, "Date Received must be YYYY-MM-DD.")
        if not 1 <= len(files) <= 8:
            raise HTTPException(400, "Choose 1–8 photos of one tube.")
        if any(file.content_type not in TYPES for file in files):
            raise HTTPException(400, "Use JPG, PNG, or WebP photos.")

        record_id = uuid4().hex
        staging = UPLOADS / (".pending-" + record_id)
        destination = UPLOADS / record_id
        staging.mkdir()
        images = []
        for number, file in enumerate(files, start=1):
            name = f"image_{number}{TYPES[file.content_type]}"
            size = 0
            digest=hashlib.sha256()
            with (staging / name).open("wb") as output:
                while True:
                    chunk = file.file.read(64 * 1024)
                    if not chunk:
                        break
                    size += len(chunk)
                    if size > 10 * 1024 * 1024:
                        raise HTTPException(413, "Maximum 10 MB per photo.")
                    output.write(chunk)
                    digest.update(chunk)
            if not size:
                raise HTTPException(400, "Empty photo.")
            images.append({"filename": name, "size_bytes": size, "sha256":digest.hexdigest()})

        sample = {
            "record_id": record_id, "session_id": session_id,
            "created_at": STORE.now(), "date_received": date_received,
            "images": images, "image_count": len(images),
        }
        (staging / "sample.json").write_text(
            json.dumps(sample, indent=2), encoding="utf-8")
        staging.rename(destination)
        STORE.register(session_id, record_id, sample=sample)
        completed = True
        return {"record_id": record_id, "state": "queued"}

    except OSError:
        raise HTTPException(500, "Could not save photos. Check Pi storage.")
    finally:
        try:
            if staging is not None and staging.exists():
                shutil.rmtree(staging)
            if not completed and destination is not None and destination.exists():
                shutil.rmtree(destination)
        finally:
            for file in files:
                file.file.close()


@app.post('/upload-batch')
def upload_batch(archive: UploadFile = File(...), session_id: str = Form(...),
                 date_received: str = Form(...)):
    moved = []
    committed = False
    try:
        STORE.require_active(session_id)
        if not valid_received(date_received):
            raise HTTPException(400, 'Date Received must be YYYY-MM-DD.')
        with tempfile.TemporaryDirectory(dir=UPLOADS, prefix='.batch-') as temporary:
            staging = Path(temporary)
            samples = prepare_archive(archive.file, staging, session_id, date_received, STORE.now())
            for sample in samples:
                destination = UPLOADS/sample['record_id']
                (staging/sample['record_id']).rename(destination)
                moved.append(destination)
            STORE.register_batch(session_id, [s['record_id'] for s in samples],
                                 samples={s['record_id']:s for s in samples})
            committed = True
        return {'queued_samples':len(samples), 'record_ids':[s['record_id'] for s in samples]}
    except (BatchImportError, zipfile.BadZipFile, NotImplementedError) as error:
        raise HTTPException(400, str(error))
    except OSError:
        raise HTTPException(500, 'Could not import ZIP. Check Pi storage.')
    finally:
        archive.file.close()
        if not committed:
            for folder in moved:
                shutil.rmtree(folder, ignore_errors=True)
