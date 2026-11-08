import json
import logging
import re
import subprocess
import sys
import tempfile
import threading
import time
from datetime import datetime
from pathlib import Path
from uuid import uuid4
from session_store import SessionStore, SessionError

class QueueStore(SessionStore):
    def __init__(self, path):
        super().__init__(path)
        with self.connection() as db:
            db.execute("""
                CREATE TABLE IF NOT EXISTS scan_jobs (
                    record_id TEXT PRIMARY KEY
                        REFERENCES session_samples(record_id),
                    state TEXT NOT NULL,
                    error TEXT,
                    notices_json TEXT NOT NULL DEFAULT '[]'
                )
            """)
            columns = {row['name'] for row in db.execute('PRAGMA table_info(scan_jobs)')}
            for name, kind in [('queued_at', 'REAL'), ('timing_json', 'TEXT')]:
                if name not in columns:
                    db.execute(f'ALTER TABLE scan_jobs ADD COLUMN {name} {kind}')

    def register(self, session_id, record_id):
        with self.connection(write=True) as db:
            self._active(db, session_id)
            self._attach(db, session_id, record_id)
            db.execute("""
                INSERT OR IGNORE INTO scan_jobs(record_id, state, queued_at)
                VALUES (?, 'queued', ?)
            """, (record_id, time.time()))

    def recover(self):
        with self.connection(write=True) as db:
            db.execute("""
                UPDATE scan_jobs SET state='queued', queued_at=NULL, timing_json=NULL
                WHERE state='processing'
            """)

    def claim(self):
        with self.connection(write=True) as db:
            row = db.execute("""
                SELECT j.record_id, s.session_id, j.queued_at
                FROM scan_jobs j JOIN session_samples s USING(record_id)
                WHERE j.state='queued'
                ORDER BY s.sequence LIMIT 1
            """).fetchone()
            if row is None:
                return None
            db.execute("""
                UPDATE scan_jobs SET state='processing', error=NULL
                WHERE record_id=?
            """, (row["record_id"],))
            job = dict(row)
            job['queue_seconds'] = max(0, time.time()-row['queued_at']) if row['queued_at'] is not None else None
            return job

    def complete(self, job, review, notices, processing_seconds=None):
        timing = None
        if processing_seconds is not None:
            waiting = job.get('queue_seconds')
            timing = {'processing_seconds': processing_seconds, 'queue_seconds': waiting,
                      'total_seconds': waiting+processing_seconds if waiting is not None else None}
        with self.connection(write=True) as db:
            db.execute("""
                UPDATE session_samples SET review_json=?
                WHERE record_id=? AND session_id=?
            """, (json.dumps(review), job["record_id"], job["session_id"]))
            db.execute("""
                UPDATE scan_jobs SET state='done', error=NULL, notices_json=?, timing_json=?
                WHERE record_id=?
            """, (json.dumps(notices), json.dumps(timing), job["record_id"]))

    def fail(self, record_id, error):
        with self.connection(write=True) as db:
            db.execute("""
                UPDATE scan_jobs SET state='error', error=?
                WHERE record_id=? AND state='processing'
            """, (str(error)[:500], record_id))

    def retry(self, session_id, record_id):
        with self.connection(write=True) as db:
            self._active(db, session_id)
            row = db.execute("""
                SELECT j.state FROM scan_jobs j
                JOIN session_samples s USING(record_id)
                WHERE s.session_id=? AND j.record_id=?
            """, (session_id, record_id)).fetchone()
            if row is None:
                raise SessionError("Queued sample not found.")
            if row["state"] == "error":
                db.execute("""
                    UPDATE scan_jobs SET state='queued', error=NULL, queued_at=?, timing_json=NULL
                    WHERE record_id=?
                """, (time.time(), record_id))

    def status(self, session_id):
        with self.connection() as db:
            result = self._session(db, session_id)
            counts = db.execute("""
                SELECT j.state, COUNT(*) AS total FROM scan_jobs j
                JOIN session_samples s USING(record_id)
                WHERE s.session_id=? GROUP BY j.state
            """, (session_id,)).fetchall()
            result["counts"] = {row["state"]: row["total"] for row in counts}
            rows = db.execute("""
                SELECT s.record_id, s.sequence, s.review_json,
                       j.state, j.error, j.notices_json, j.timing_json
                FROM session_samples s JOIN scan_jobs j USING(record_id)
                WHERE s.session_id=? ORDER BY s.sequence
            """, (session_id,)).fetchall()
            result["jobs"] = []
            result["confirmed_count"] = 0
            result["ready_count"] = 0
            for row in rows:
                review = json.loads(row["review_json"]) if row["review_json"] else {}
                confirmed = bool(review.get("confirmed", False))
                result["confirmed_count"] += int(confirmed)
                result["ready_count"] += int(row["state"] == "done" and not confirmed)
                result["jobs"].append({
                    "record_id": row["record_id"],
                    "sequence": row["sequence"],
                    "sample_id": review.get("fields", {}).get("sample_id", ""),
                    "state": row["state"], "error": row["error"],
                    "notices": json.loads(row["notices_json"]),
                    "timing": json.loads(row['timing_json']) if row['timing_json'] else None,
                    "review": {
                        key: review.get(key) for key in (
                            "fields", "label_type", "confirmed",
                            "image_count", "evidence"
                        )
                    } if review else None,
                })
            return result

    def confirmed_reviews(self, session_id):
        return [
            review for review in self.reviews(session_id)
            if review.get("confirmed")
        ]

    def edit(self, session_id, record_id, fields, kind, confirmed):
        with self.connection(write=True) as db:
            self._active(db, session_id)
            row = db.execute("""
                SELECT s.review_json, j.state FROM session_samples s
                JOIN scan_jobs j USING(record_id)
                WHERE s.session_id=? AND s.record_id=?
            """, (session_id, record_id)).fetchone()
            if row is None or row["state"] != "done" or not row["review_json"]:
                raise SessionError("This sample is not ready for review.")
            review = json.loads(row["review_json"])
            review.update(
                fields=fields, label_type=kind, confirmed=confirmed,
                saved_at=self.now(),
                reviewed_at=self.now() if confirmed else None,
            )
            db.execute("""
                UPDATE session_samples SET review_json=?
                WHERE record_id=?
            """, (json.dumps(review), record_id))
            return review

def normalized_date(value):
    # Preserve the written date without guessing its meaning or year.
    return str(value or "").strip()


class ScannerQueue:
    def __init__(self, store, base_dir):
        self.store = store
        self.base = Path(base_dir)
        self.stopping = threading.Event()
        self.thread = None

    def start(self):
        self.store.recover()
        self.thread = threading.Thread(target=self.loop, daemon=True)
        self.thread.start()

    def stop(self):
        self.stopping.set()
        if self.thread:
            self.thread.join(timeout=12)

    def loop(self):
        while not self.stopping.is_set():
            job = None
            try:
                job = self.store.claim()
                if job:
                    self.process(job)
                else:
                    self.stopping.wait(0.5)
            except InterruptedError:
                return
            except Exception as error:
                logging.exception("Background scan failed")
                if job:
                    try:
                        self.store.fail(job["record_id"], error)
                    except Exception:
                        logging.exception("Could not update scan status")
                self.stopping.wait(1)

    def child(self, command, timeout):
        with tempfile.TemporaryFile() as log:
            process = subprocess.Popen(
                command, cwd=self.base, stdout=log, stderr=log)
            deadline = time.monotonic() + timeout
            try:
                while process.poll() is None:
                    if self.stopping.wait(0.25):
                        raise InterruptedError("Server stopping")
                    if time.monotonic() > deadline:
                        raise RuntimeError("Reading timed out. Try a clearer photo.")
                if process.returncode:
                    raise RuntimeError(
                        "OCR worker stopped. Check Pi memory and models.")
            finally:
                if process.poll() is None:
                    process.terminate()
                    try:
                        process.wait(timeout=5)
                    except subprocess.TimeoutExpired:
                        process.kill()
                        process.wait()

    def snapshot(self, path, value):
        temporary = path.with_name("." + path.name + "-" + uuid4().hex)
        try:
            temporary.write_text(json.dumps(value, indent=2), encoding="utf-8")
            temporary.replace(path)
        finally:
            temporary.unlink(missing_ok=True)

    def process(self, job):
        processing_started = time.perf_counter()
        record_id = job["record_id"]
        if not re.fullmatch(r"[0-9a-f]{32}", record_id):
            raise RuntimeError("Invalid record ID.")
        folder = self.base / "uploads" / record_id
        sample = json.loads(
            (folder / "sample.json").read_text(encoding="utf-8"))
        names = [entry["filename"] for entry in sample["images"]]
        if not 1 <= len(names) <= 8 or any(
            not re.fullmatch(r"image_[1-8]\.(jpg|png|webp)", name)
            for name in names
        ):
            raise RuntimeError("Invalid image record.")

        run_id = uuid4().hex
        with tempfile.TemporaryDirectory() as temporary:
            request = Path(temporary) / "job.json"
            output = Path(temporary) / "output.json"
            request.write_text(json.dumps({
                "images": [str((folder / name).resolve()) for name in names],
                "debug_dir": str((folder / "analysis" / run_id).resolve()),
            }), encoding="utf-8")
            self.child([
                sys.executable, str(self.base / "scanner_auto.py"),
                str(request), str(output),
            ], timeout=180 * len(names) + 60)
            result = json.loads(output.read_text(encoding="utf-8"))
        if result.get("error"):
            raise RuntimeError(result["error"])

        kind = result.get("label_type", "unknown")
        if kind not in {"small", "large"}:
            kind = "unknown"
        raw = result.get("suggestions", {})
        titles = {
            "sample_id": "Sample ID", "date_sampled": "Date Sampled",
            "machine": "Machine", "component": "Component",
            "serial_number": "Serial Number", "reference_lube": "Reference Lube",
        }
        fields = {key: str(raw.get(key) or "").strip() for key in titles}
        fields["date_sampled"] = normalized_date(fields["date_sampled"])
        fields["date_received"] = sample["date_received"]
        fields["serial_number"] = fields["serial_number"].upper()
        notices = []

        if kind == "small":
            fields["reference_lube"] = ""
            fields["component"] = fields["component"].upper()
            if fields["component"] and not re.fullmatch(
                r"[1-6] (?:GS|NGS)", fields["component"]
            ):
                fields["component"] = ""
        elif kind == "large":
            fields["serial_number"] = ""
        else:
            notices.append("Label type needs checking.")
            for key in ("machine", "component", "serial_number", "reference_lube"):
                fields[key] = ""

        review = {
            "record_id": record_id, "session_id": job["session_id"],
            "label_type": kind, "saved_at": self.store.now(),
            "confirmed": False, "reviewed_at": None,
            "fields": fields, "raw_suggestions": raw,
            "image_count": len(names),
        }
        try:
            from label_preview import build_preview
            review["evidence"] = build_preview(folder, run_id, result, kind)
        except Exception:
            logging.exception("Could not build combined label view")
            review["evidence"] = None

        result.update(record_id=record_id, run_id=run_id)
        self.store.complete(job, review, notices,
                            processing_seconds=time.perf_counter()-processing_started)
        try:
            self.snapshot(folder / "ocr.json", result)
            self.snapshot(folder / "review.json", review)
        except OSError:
            logging.exception("Database saved; JSON snapshot failed")
