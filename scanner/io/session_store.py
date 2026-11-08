import json
import sqlite3
from contextlib import contextmanager
from datetime import datetime, timezone
from uuid import uuid4


class SessionError(Exception):
    pass


class SessionStore:
    def __init__(self, path):
        self.path = str(path)

        with self.connection() as db:
            db.executescript("""
                CREATE TABLE IF NOT EXISTS sessions (
                    id TEXT PRIMARY KEY,
                    name TEXT NOT NULL,
                    created_at TEXT NOT NULL,
                    finished_at TEXT
                );

                CREATE TABLE IF NOT EXISTS session_samples (
                    sequence INTEGER PRIMARY KEY AUTOINCREMENT,
                    record_id TEXT NOT NULL UNIQUE,
                    session_id TEXT NOT NULL REFERENCES sessions(id),
                    added_at TEXT NOT NULL,
                    review_json TEXT
                );

                CREATE INDEX IF NOT EXISTS samples_session
                ON session_samples(session_id, sequence);
            """)

    @staticmethod
    def now():
        return datetime.now(timezone.utc).isoformat()

    @contextmanager
    def connection(self, write=False):
        db = sqlite3.connect(self.path, timeout=15)
        db.row_factory = sqlite3.Row
        db.execute("PRAGMA foreign_keys = ON")

        try:
            if write:
                db.execute("BEGIN IMMEDIATE")

            with db:
                yield db
        finally:
            db.close()

    def _session(self, db, session_id):
        row = db.execute(
            "SELECT * FROM sessions WHERE id = ?",
            (session_id,),
        ).fetchone()

        if row is None:
            raise SessionError("Session not found.")

        result = dict(row)

        counts = db.execute("""
            SELECT COUNT(*) AS total,
                   COUNT(review_json) AS saved_count
            FROM session_samples
            WHERE session_id = ?
        """, (session_id,)).fetchone()

        result["saved_count"] = counts["saved_count"]
        result["pending_count"] = (
            counts["total"] - counts["saved_count"]
        )

        return result

    def get(self, session_id):
        with self.connection() as db:
            return self._session(db, session_id)

    def list(self):
        with self.connection() as db:
            rows = db.execute("""
                SELECT id FROM sessions
                ORDER BY created_at DESC
                LIMIT 50
            """).fetchall()

            return [
                self._session(db, row["id"])
                for row in rows
            ]

    def create(self, name):
        session_id = uuid4().hex
        name = name.strip() or "Scanning session"

        with self.connection(write=True) as db:
            db.execute("""
                INSERT INTO sessions(id, name, created_at)
                VALUES (?, ?, ?)
            """, (session_id, name, self.now()))

            return self._session(db, session_id)

    def _active(self, db, session_id):
        session = self._session(db, session_id)

        if session["finished_at"]:
            raise SessionError(
                "This session is finished. Start a new session."
            )

        return session

    def require_active(self, session_id):
        with self.connection() as db:
            return self._active(db, session_id)

    def _attach(self, db, session_id, record_id):
        existing = db.execute("""
            SELECT session_id
            FROM session_samples
            WHERE record_id = ?
        """, (record_id,)).fetchone()

        if existing:
            if existing["session_id"] != session_id:
                raise SessionError(
                    "This sample belongs to another session."
                )
            return

        db.execute("""
            INSERT INTO session_samples(
                record_id, session_id, added_at
            )
            VALUES (?, ?, ?)
        """, (record_id, session_id, self.now()))

    def attach(self, session_id, record_id):
        with self.connection(write=True) as db:
            self._active(db, session_id)
            self._attach(db, session_id, record_id)

    def sample(self, record_id):
        with self.connection() as db:
            row = db.execute("""
                SELECT session_id, review_json
                FROM session_samples
                WHERE record_id = ?
            """, (record_id,)).fetchone()

            if row is None:
                return None

            return {
                "session_id": row["session_id"],
                "review": (
                    json.loads(row["review_json"])
                    if row["review_json"]
                    else None
                ),
            }

    def save(self, session_id, record_id, review):
        with self.connection(write=True) as db:
            self._active(db, session_id)
            self._attach(db, session_id, record_id)

            # Update the existing sample instead of adding another row.
            db.execute("""
                UPDATE session_samples
                SET review_json = ?
                WHERE record_id = ? AND session_id = ?
            """, (
                json.dumps(review),
                record_id,
                session_id,
            ))

            return self._session(db, session_id)

    def finish(self, session_id):
        with self.connection(write=True) as db:
            self._session(db, session_id)

            db.execute("""
                UPDATE sessions
                SET finished_at = COALESCE(finished_at, ?)
                WHERE id = ?
            """, (self.now(), session_id))

            return self._session(db, session_id)

    def reviews(self, session_id):
        with self.connection() as db:
            self._session(db, session_id)

            rows = db.execute("""
                SELECT review_json
                FROM session_samples
                WHERE session_id = ?
                  AND review_json IS NOT NULL
                ORDER BY sequence
            """, (session_id,)).fetchall()

            return [
                json.loads(row["review_json"])
                for row in rows
            ]