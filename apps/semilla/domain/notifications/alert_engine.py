
"""Alert Engine - alertas automaticas (SM1)."""
from __future__ import annotations
from typing import List
import uuid
from shared_engines.common.clocks import Clock
from shared_engines.storage.database import (
    Database)
from shared_engines.storage.migrations import (
    Migration, MigrationRunner)

ALERT_TYPES = ("ABSENCE", "GRADE_POSTED",
               "EXAM_UPCOMING", "BEHAVIOR",
               "HEALTH", "GENERAL")
ROLES = ("PARENT", "TEACHER", "INSTITUTION")

_MIGRATIONS = (
    Migration(1, "sm_alerts", (
        "CREATE TABLE IF NOT EXISTS sm_alerts (alert_id TEXT PRIMARY KEY, student_id TEXT NOT NULL, alert_type TEXT NOT NULL, title TEXT NOT NULL, detail TEXT NOT NULL DEFAULT '', recipient_role TEXT NOT NULL DEFAULT 'PARENT', recipient_ref TEXT NOT NULL DEFAULT '', read INTEGER NOT NULL DEFAULT 0, created_at REAL NOT NULL)",
    )),
)

class AlertEngine:
    """Alertas del ciclo escolar (persistente)."""

    def __init__(self, db, clock):
        self._db = db
        self._clock = clock
        MigrationRunner(db, "sm.alerts",
                        _MIGRATIONS).run(clock)

    def publish(self, *, student_id, alert_type,
                title, detail="",
                recipient_role="PARENT",
                recipient_ref="") -> dict:
        if alert_type not in ALERT_TYPES:
            raise ValueError(
                "tipo de alerta invalido")
        if recipient_role not in ROLES:
            raise ValueError("rol invalido")
        aid = "SMALR-" + str(uuid.uuid4())
        now = self._clock.now()
        with self._db.transaction() as cursor:
            cursor.execute(
                "INSERT INTO sm_alerts"
                " (alert_id, student_id,"
                " alert_type, title, detail,"
                " recipient_role, recipient_ref,"
                " read, created_at)"
                " VALUES (?, ?, ?, ?, ?, ?, ?,"
                " 0, ?)",
                (aid, student_id, alert_type,
                 str(title).strip(),
                 str(detail), recipient_role,
                 str(recipient_ref), now))
        return {"alert_id": aid,
                "alert_type": alert_type}

    def mark_read(self, alert_id) -> dict:
        self._db.execute(
            "UPDATE sm_alerts SET read = 1"
            " WHERE alert_id = ?",
            (alert_id,))
        row = self._db.query_one(
            "SELECT alert_id FROM sm_alerts"
            " WHERE alert_id = ?", (alert_id,))
        if not row:
            raise KeyError(alert_id)
        return {"alert_id": str(alert_id),
                "read": True}

    def unread(self, student_id,
               recipient_role="PARENT"
               ) -> List[dict]:
        rows = self._db.query_all(
            "SELECT * FROM sm_alerts WHERE"
            " student_id = ? AND read = 0 AND"
            " recipient_role = ?"
            " ORDER BY created_at",
            (student_id, recipient_role))
        return [{"alert_id":
                     str(r["alert_id"]),
                 "alert_type":
                     str(r["alert_type"]),
                 "title": str(r["title"]),
                 "detail": str(r["detail"])}
                for r in rows]

    def alerts_of(self, student_id,
                  limit=100) -> List[dict]:
        rows = self._db.query_all(
            "SELECT * FROM sm_alerts WHERE"
            " student_id = ? ORDER BY"
            " created_at DESC LIMIT ?",
            (student_id, limit))
        return [{"alert_id":
                     str(r["alert_id"]),
                 "alert_type":
                     str(r["alert_type"]),
                 "title": str(r["title"]),
                 "detail": str(r["detail"]),
                 "read": bool(r["read"]),
                 "created_at":
                     float(r["created_at"])}
                for r in rows]
