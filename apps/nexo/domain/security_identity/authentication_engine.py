
"""Nexo Authentication Engine - sesiones (NG8)."""
from __future__ import annotations
from typing import Optional
import uuid
from shared_engines.common.clocks import Clock
from shared_engines.storage.database import Database
from shared_engines.storage.migrations import (
    Migration, MigrationRunner)

_MIGRATIONS = (
    Migration(1, "nexo_sessions", (
        "CREATE TABLE IF NOT EXISTS nexo_sessions (session_id TEXT PRIMARY KEY, zid TEXT NOT NULL, status TEXT NOT NULL DEFAULT 'ACTIVE', created_at REAL NOT NULL, expires_at REAL NOT NULL, ended_at REAL)",
    )),
)

class NexoAuthenticationEngine:
    """Sesiones por ZID (referencias)."""

    def __init__(self, db, clock):
        self._db = db
        self._clock = clock
        MigrationRunner(db, "nexo.sessions",
                        _MIGRATIONS).run(clock)

    def open_session(self, *, zid,
                     ttl_seconds=3600) -> dict:
        if not str(zid).strip():
            raise ValueError("zid requerido")
        sid = "SES-" + str(uuid.uuid4())
        now = self._clock.now()
        with self._db.transaction() as cursor:
            cursor.execute(
                "INSERT INTO nexo_sessions"
                " (session_id, zid, status,"
                " created_at, expires_at,"
                " ended_at)"
                " VALUES (?, ?, 'ACTIVE', ?, ?,"
                " NULL)",
                (sid, zid, now,
                 now + int(ttl_seconds)))
        return self.get_session(sid)

    def get_session(self,
                    session_id) -> Optional[dict]:
        row = self._db.query_one(
            "SELECT * FROM nexo_sessions WHERE"
            " session_id = ?", (session_id,))
        if not row:
            return None
        return {"session_id":
                    str(row["session_id"]),
                "zid": str(row["zid"]),
                "status": str(row["status"]),
                "created_at":
                    float(row["created_at"]),
                "expires_at":
                    float(row["expires_at"])}

    def active_session(self, zid) -> Optional[dict]:
        now = self._clock.now()
        row = self._db.query_one(
            "SELECT session_id FROM nexo_sessions"
            " WHERE zid = ? AND status = 'ACTIVE'"
            " AND expires_at > ?"
            " ORDER BY created_at DESC LIMIT 1",
            (zid, now))
        if not row:
            return None
        return self.get_session(
            str(row["session_id"]))

    def end_session(self, session_id) -> dict:
        self._db.execute(
            "UPDATE nexo_sessions SET status ="
            " 'ENDED', ended_at = ? WHERE"
            " session_id = ?",
            (self._clock.now(), session_id))
        return self.get_session(session_id)
