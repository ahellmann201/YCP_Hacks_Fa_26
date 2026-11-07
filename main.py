import csv
import io
import json
import re
import shutil
import subprocess
import sys
import tempfile
import threading

from datetime import date, datetime, timezone
from pathlib import Path
from typing import List, Literal
from uuid import uuid4

from fastapi import FastAPI, File, Form, HTTPException, UploadFile
from fastapi.responses import FileResponse, Response
from pydantic import BaseModel, Field


app = FastAPI()

BASE_DIR = Path(__file__).resolve().parent
UPLOAD_DIR = BASE_DIR / "uploads"
UPLOAD_DIR.mkdir(exist_ok=True)

OCR_LOCK = threading.Lock()

TYPES = {
    "image/jpeg": ".jpg",
    "image/png": ".png",
    "image/webp": ".webp",
}

COLUMNS = [
    ("sample_id", "Sample ID"),
    ("date_sampled", "Date Sampled"),
    ("date_received", "Date Received"),
    ("machine", "Machine"),
    ("component", "Component"),
    ("serial_number", "Serial Number"),
    ("reference_lube", "Reference Lube"),
]


def now():
    return datetime.now(timezone.utc).isoformat()


def read_json(path):
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        raise HTTPException(500, "Could not read the saved record.")


def write_json(path, data):
    temporary = path.with_name(f".{path.name}-{uuid4().hex}.tmp")

    try:
        temporary.write_text(
            json.dumps(data, indent=2),
            encoding="utf-8",
        )
        temporary.replace(path)
    except OSError:
        raise HTTPException(500, "Could not save. Check Pi storage.")
    finally:
        temporary.unlink(missing_ok=True)


def folder_for(record_id):
    if not re.fullmatch(r"[0-9a-f]{32}", record_id):
        raise HTTPException(404, "Sample not found.")

    folder = UPLOAD_DIR / record_id

    if not (folder / "sample.json").is_file():
        raise HTTPException(404, "Sample not found.")

    return folder


def names_for(folder):
    record = read_json(folder / "sample.json")
    names = [entry.get("filename", "") for entry in record["images"]]

    if not 1 <= len(names) <= 8:
        raise HTTPException(500, "Invalid image count.")

    if any(
        not re.fullmatch(r"image_[1-8]\.(jpg|png|webp)", name)
        for name in names
    ):
        raise HTTPException(500, "Invalid image record.")

    return names


def check_date(value):
    try:
        date.fromisoformat(value)
    except ValueError:
        raise HTTPException(400, "Date received must use YYYY-MM-DD.")


class Fields(BaseModel):
    sample_id: str = Field(default="", max_length=200)
    date_sampled: str = Field(default="", max_length=200)
    date_received: str = Field(max_length=10)
    machine: str = Field(default="", max_length=200)
    component: str = Field(default="", max_length=200)
    serial_number: str = Field(default="", max_length=200)
    reference_lube: str = Field(default="", max_length=200)


class Review(BaseModel):
    label_type: Literal["small", "large"]
    fields: Fields


@app.get("/")
def home():
    return FileResponse(
        BASE_DIR / "static" / "index.html",
        headers={"Cache-Control": "no-store"},
    )


@app.post("/upload")
def upload(
    files: List[UploadFile] = File(...),
    date_received: str = Form(...),
):
    staging = None

    try:
        check_date(date_received)

        if not 1 <= len(files) <= 8:
            raise HTTPException(400, "Choose 1–8 photos of one tube.")

        if any(file.content_type not in TYPES for file in files):
            raise HTTPException(400, "Use JPG, PNG, or WebP photos.")

        record_id = uuid4().hex
        staging = UPLOAD_DIR / f".pending-{record_id}"
        staging.mkdir()

        images = []

        for number, upload_file in enumerate(files, start=1):
            name = f"image_{number}{TYPES[upload_file.content_type]}"
            size = 0

            with (staging / name).open("wb") as output:
                while True:
                    chunk = upload_file.file.read(64 * 1024)

                    if not chunk:
                        break

                    size += len(chunk)

                    if size > 10 * 1024 * 1024:
                        raise HTTPException(413, "Maximum 10 MB per photo.")

                    output.write(chunk)

            if not size:
                raise HTTPException(400, "Empty photo.")

            images.append({
                "filename": name,
                "size_bytes": size,
            })

        record = {
            "record_id": record_id,
            "created_at": now(),
            "date_received": date_received,
            "images": images,
            "image_count": len(images),
        }

        write_json(staging / "sample.json", record)
        staging.rename(UPLOAD_DIR / record_id)

        return {"record_id": record_id}

    except OSError:
        raise HTTPException(500, "Could not save uploaded photos.")

    finally:
        try:
            if staging is not None and staging.exists():
                shutil.rmtree(staging)
        finally:
            for upload_file in files:
                upload_file.file.close()


@app.get("/samples/{record_id}")
def get_sample(record_id: str):
    folder = folder_for(record_id)

    return {
        "sample": read_json(folder / "sample.json"),
        "ocr": (
            read_json(folder / "ocr.json")
            if (folder / "ocr.json").exists()
            else None
        ),
        "review": (
            read_json(folder / "review.json")
            if (folder / "review.json").exists()
            else None
        ),
    }


@app.get("/samples/{record_id}/images/{number}")
def image(record_id: str, number: int):
    folder = folder_for(record_id)
    names = names_for(folder)

    if not 1 <= number <= len(names):
        raise HTTPException(404, "Photo not found.")

    path = folder / names[number - 1]

    if not path.is_file():
        raise HTTPException(404, "Photo not found.")

    return FileResponse(path)


@app.get("/samples/{record_id}/debug/{run_id}/{filename}")
def debug_image(record_id: str, run_id: str, filename: str):
    folder = folder_for(record_id)

    if not re.fullmatch(r"[0-9a-f]{32}", run_id):
        raise HTTPException(404, "Image not found.")

    if not re.fullmatch(r"photo_[1-8]_[a-z_]+\.jpg", filename):
        raise HTTPException(404, "Image not found.")

    path = folder / "analysis" / run_id / filename

    if not path.is_file():
        raise HTTPException(404, "Image not found.")

    return FileResponse(path)


@app.post("/samples/{record_id}/ocr")
def automatic_ocr(record_id: str):
    folder = folder_for(record_id)

    if not OCR_LOCK.acquire(blocking=False):
        raise HTTPException(409, "The Pi is reading another sample.")

    try:
        names = names_for(folder)
        run_id = uuid4().hex
        debug_dir = folder / "analysis" / run_id

        with tempfile.TemporaryDirectory() as temporary:
            job_path = Path(temporary) / "job.json"
            output_path = Path(temporary) / "output.json"

            job_path.write_text(
                json.dumps({
                    "images": [
                        str((folder / name).resolve())
                        for name in names
                    ],
                    "debug_dir": str(debug_dir.resolve()),
                }),
                encoding="utf-8",
            )

            with tempfile.TemporaryFile() as log:
                try:
                    completed = subprocess.run(
                        [
                            sys.executable,
                            str(BASE_DIR / "scanner_auto.py"),
                            str(job_path),
                            str(output_path),
                        ],
                        cwd=BASE_DIR,
                        stdout=log,
                        stderr=log,
                        timeout=180 * len(names) + 60,
                    )
                except subprocess.TimeoutExpired:
                    raise HTTPException(
                        504,
                        "Reading timed out. Try fewer or smaller photos.",
                    )

            if completed.returncode != 0 or not output_path.exists():
                raise HTTPException(
                    500,
                    "OCR worker stopped. Check its packages and Pi memory.",
                )

            result = read_json(output_path)

        if result.get("error"):
            raise HTTPException(422, result["error"])

        result.update({
            "record_id": record_id,
            "run_id": run_id,
            "processed_at": now(),
        })

        write_json(folder / "ocr.json", result)
        return result

    except OSError:
        raise HTTPException(500, "Could not start automatic reading.")

    finally:
        OCR_LOCK.release()


@app.post("/samples/{record_id}/review")
def save_review(record_id: str, review: Review):
    folder = folder_for(record_id)
    fields = {
        key: value.strip()
        for key, value in review.fields.model_dump().items()
    }

    check_date(fields["date_received"])

    if review.label_type == "small":
        fields["reference_lube"] = ""

        if fields["component"] and not re.fullmatch(
            r"[1-6] (?:GS|NGS)",
            fields["component"],
        ):
            raise HTTPException(400, "Component must look like 4 GS.")
    else:
        fields["serial_number"] = ""

    record = {
        "record_id": record_id,
        "label_type": review.label_type,
        "reviewed_at": now(),
        "fields": fields,
    }

    write_json(folder / "review.json", record)
    return {"review": record}


@app.get("/samples/{record_id}/csv")
def csv_export(record_id: str):
    folder = folder_for(record_id)
    path = folder / "review.json"

    if not path.exists():
        raise HTTPException(400, "Save the reviewed fields first.")

    fields = read_json(path)["fields"]
    output = io.StringIO(newline="")
    writer = csv.writer(output)

    writer.writerow([title for _, title in COLUMNS])
    writer.writerow([fields.get(key, "") for key, _ in COLUMNS])

    return Response(
        output.getvalue().encode("utf-8-sig"),
        media_type="text/csv",
        headers={
            "Content-Disposition":
                f'attachment; filename="sample-{record_id}.csv"'
        },
    )