
"""Psychology Engine - apoyo psicológico escolar
(SM4). Sesiones confidenciales + derivaciones."""
from __future__ import annotations
from typing import List, Optional
import uuid
from shared_engines.common.clocks import Clock
from shared_engines.storage.database import (
    Database)
from shared_engines.storage.migrations import (
    Migration, MigrationRunner)

_MIGRATIONS = (
    Migration(1, "sm_psych_sessions", (
        "CREATE TABLE IF NOT EXISTS sm_psych_sessions (session_id TEXT PRIMARY KEY, student_id TEXT NOT NULL, psychologist TEXT NOT NULL, scheduled_date TEXT NOT NULL, reason TEXT NOT NULL DEFAULT '', notes TEXT NOT NULL DEFAULT '', followup TEXT NOT NULL DEFAULT '', status TEXT NOT NULL DEFAULT 'SCHEDULED', created_at REAL NOT NULL)",
    )),
    Migration(2, "sm_psych_refs", (
        "CREATE TABLE IF NOT EXISTS sm_psych_refs (ref_id TEXT PRIMARY KEY, student_id TEXT NOT NULL, institution TEXT NOT NULL, reason TEXT NOT NULL DEFAULT '', created_at REAL NOT NULL)",
    )),
)

class PsychologyEngine:
    """Apoyo psicológico (referencial)."""

    def __init__(self, db, clock):
        self._db = db
        self._clock = clock
        MigrationRunner(db, "sm.psych",
                        _MIGRATIONS).run(clock)

    def schedule_session(self, *, student_id,
                         psychologist,
                         scheduled_date,
                         reason="") -> dict:
        if not str(psychologist).strip():
            raise ValueError(
                "psychologist requerido")
        if not str(scheduled_date).strip():
            raise ValueError(
                "scheduled_date requerido")
        sid = "SMPSY-" + str(uuid.uuid4())
        now = self._clock.now()
        with self._db.transaction() as cursor:
            cursor.execute(
                "INSERT INTO sm_psych_sessions"
                " (session_id, student_id,"
                " psychologist, scheduled_date,"
                " reason, status, created_at)"
                " VALUES (?, ?, ?, ?, ?,"
                " 'SCHEDULED', ?)",
                (sid, student_id,
                 str(psychologist).strip(),
                 str(scheduled_date),
                 str(reason), now))
        return self.get_session(sid)

    def get_session(self, session_id
                    ) -> Optional[dict]:
        row = self._db.query_one(
            "SELECT * FROM sm_psych_sessions"
            " WHERE session_id = ?",
            (session_id,))
        if not row:
            return None
        return {"session_id":
                    str(row["session_id"]),
                "student_id":
                    str(row["student_id"]),
                "psychologist":
                    str(row["psychologist"]),
                "scheduled_date":
                    str(row["scheduled_date"]),
                "reason": str(row["reason"]),
                "notes": str(row["notes"]),
                "followup":
                    str(row["followup"]),
                "status": str(row["status"])}

    def record_session(self, *, session_id,
                       notes, followup="") -> dict:
        row = self._db.query_one(
            "SELECT status FROM sm_psych_sessions"
            " WHERE session_id = ?",
            (session_id,))
        if not row:
            raise KeyError(session_id)
        if str(row["status"]) != "SCHEDULED":
            raise ValueError(
                "solo SCHEDULED se completa")
        self._db.execute(
            "UPDATE sm_psych_sessions SET"
            " notes = ?, followup = ?, status ="
            " 'COMPLETED' WHERE session_id = ?",
            (str(notes), str(followup),
             session_id))
        return self.get_session(session_id)

    def refer_external(self, *, student_id,
                       institution,
                       reason="") -> dict:
        if not str(institution).strip():
            raise ValueError(
                "institution requerido")
        rid = "SMREF-" + str(uuid.uuid4())
        now = self._clock.now()
        with self._db.transaction() as cursor:
            cursor.execute(
                "INSERT INTO sm_psych_refs"
                " (ref_id, student_id,"
                " institution, reason, created_at)"
                " VALUES (?, ?, ?, ?, ?)",
                (rid, student_id,
                 str(institution).strip(),
                 str(reason), now))
        return {"ref_id": rid,
                "student_id": student_id,
                "institution":
                    str(institution).strip(),
                "status": "REFERRED"}

    def sessions_of(self, student_id
                    ) -> List[dict]:
        rows = self._db.query_all(
            "SELECT session_id FROM"
            " sm_psych_sessions WHERE"
            " student_id = ? ORDER BY"
            " created_at", (student_id,))
        return [self.get_session(
            str(r["session_id"]))
            for r in rows]
