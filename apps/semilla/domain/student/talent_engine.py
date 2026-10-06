
"""Talent Engine - registro nacional de talento
(SM3). Detectar -> mentoria -> aceleracion. Alerta
positiva al encargado. Informativo (regla 57)."""
from __future__ import annotations
from typing import List, Optional
import uuid
from shared_engines.common.clocks import Clock
from shared_engines.storage.database import (
    Database)
from shared_engines.storage.migrations import (
    Migration, MigrationRunner)

_MIGRATIONS = (
    Migration(1, "sm_talents", (
        "CREATE TABLE IF NOT EXISTS sm_talents (talent_id TEXT PRIMARY KEY, student_id TEXT NOT NULL, category TEXT NOT NULL, detail TEXT NOT NULL DEFAULT '', source TEXT NOT NULL DEFAULT 'TUTOR', score TEXT NOT NULL DEFAULT '', status TEXT NOT NULL DEFAULT 'DETECTED', mentor TEXT NOT NULL DEFAULT '', created_at REAL NOT NULL, updated_at REAL NOT NULL)",
    )),
)

class TalentEngine:
    """Talento estudiantil (persistente)."""

    def __init__(self, db, clock,
                 alert_engine=None):
        self._db = db
        self._clock = clock
        self._alerts = alert_engine
        MigrationRunner(db, "sm.talents",
                        _MIGRATIONS).run(clock)

    def register_talent(self, *, student_id,
                        category, detail="",
                        source="TUTOR",
                        score="") -> dict:
        if not str(category).strip():
            raise ValueError(
                "category requerido")
        tid = "SMTAL-" + str(uuid.uuid4())
        now = self._clock.now()
        with self._db.transaction() as cursor:
            cursor.execute(
                "INSERT INTO sm_talents"
                " (talent_id, student_id,"
                " category, detail, source, score,"
                " status, mentor, created_at,"
                " updated_at)"
                " VALUES (?, ?, ?, ?, ?, ?,"
                " 'DETECTED', '', ?, ?)",
                (tid, student_id,
                 str(category).strip(),
                 str(detail), str(source),
                 str(score), now, now))
        if self._alerts is not None:
            self._alerts.publish(
                student_id=student_id,
                alert_type="GENERAL",
                title="Talento detectado: "
                      + str(category),
                detail=(str(detail)
                        + " — felicitaciones;"
                          " la escuela dara"
                          " seguimiento"),
                recipient_role="PARENT")
        return self.get_talent(tid)

    def get_talent(self, talent_id
                   ) -> Optional[dict]:
        row = self._db.query_one(
            "SELECT * FROM sm_talents WHERE"
            " talent_id = ?", (talent_id,))
        if not row:
            return None
        return {"talent_id":
                    str(row["talent_id"]),
                "student_id":
                    str(row["student_id"]),
                "category": str(row["category"]),
                "detail": str(row["detail"]),
                "source": str(row["source"]),
                "score": str(row["score"]),
                "status": str(row["status"]),
                "mentor": str(row["mentor"])}

    def assign_mentor(self, *, talent_id,
                      mentor_name,
                      mentor_ref="") -> dict:
        t = self.get_talent(talent_id)
        if not t:
            raise KeyError(talent_id)
        if not str(mentor_name).strip():
            raise ValueError(
                "mentor_name requerido")
        self._db.execute(
            "UPDATE sm_talents SET status ="
            " 'MENTORED', mentor = ?,"
            " updated_at = ? WHERE talent_id = ?",
            (str(mentor_name).strip(),
             self._clock.now(), talent_id))
        return self.get_talent(talent_id)

    def accelerate(self, *, talent_id,
                   detail) -> dict:
        t = self.get_talent(talent_id)
        if not t:
            raise KeyError(talent_id)
        if not str(detail).strip():
            raise ValueError(
                "detail de aceleracion"
                " requerido")
        self._db.execute(
            "UPDATE sm_talents SET status ="
            " 'ACCELERATED', detail = detail ||"
            "' | ACEL: ' || ?, updated_at = ?"
            " WHERE talent_id = ?",
            (str(detail), self._clock.now(),
             talent_id))
        return self.get_talent(talent_id)

    def national_registry(self) -> List[dict]:
        rows = self._db.query_all(
            "SELECT talent_id FROM sm_talents"
            " ORDER BY created_at")
        return [self.get_talent(
            str(r["talent_id"]))
            for r in rows]

    def talents_of(self, student_id
                   ) -> List[dict]:
        rows = self._db.query_all(
            "SELECT talent_id FROM sm_talents"
            " WHERE student_id = ?"
            " ORDER BY created_at",
            (student_id,))
        return [self.get_talent(
            str(r["talent_id"]))
            for r in rows]
