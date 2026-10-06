
"""Attendance Engine - asistencia (SM1)."""
from __future__ import annotations
from typing import List, Optional
import uuid
from shared_engines.common.clocks import Clock
from shared_engines.storage.database import (
    Database)
from shared_engines.storage.migrations import (
    Migration, MigrationRunner)

ATT_STATUSES = ("PRESENTE", "AUSENTE",
                "TARDANZA", "JUSTIFICADO")

_MIGRATIONS = (
    Migration(1, "sm_attendance", (
        "CREATE TABLE IF NOT EXISTS sm_attendance (attendance_id TEXT PRIMARY KEY, student_id TEXT NOT NULL, date TEXT NOT NULL, status TEXT NOT NULL, recorded_by TEXT NOT NULL DEFAULT '', detail TEXT NOT NULL DEFAULT '', created_at REAL NOT NULL, UNIQUE(student_id, date))",
    )),
)

class AttendanceEngine:
    """Asistencia diaria con alerta de ausencia."""

    def __init__(self, db, clock,
                 alert_engine=None):
        self._db = db
        self._clock = clock
        self._alerts = alert_engine
        MigrationRunner(db, "sm.attend",
                        _MIGRATIONS).run(clock)

    def record(self, *, student_id, date,
               status, recorded_by="",
               detail="") -> dict:
        if status not in ATT_STATUSES:
            raise ValueError(
                "estado de asistencia invalido")
        if not str(date).strip():
            raise ValueError("date requerida")
        aid = "SMATT-" + str(uuid.uuid4())
        now = self._clock.now()
        with self._db.transaction() as cursor:
            dup = cursor.execute(
                "SELECT attendance_id FROM"
                " sm_attendance WHERE"
                " student_id = ? AND date = ?",
                (student_id, date)).fetchone()
            if dup is not None:
                self._db.execute(
                    "UPDATE sm_attendance SET"
                    " status = ?, recorded_by = ?,"
                    " detail = ? WHERE"
                    " attendance_id = ?",
                    (status, str(recorded_by),
                     str(detail),
                     str(dup["attendance_id"])))
                out = self.get(
                    str(dup["attendance_id"]))
                out["updated"] = True
                return out
            cursor.execute(
                "INSERT INTO sm_attendance"
                " (attendance_id, student_id,"
                " date, status, recorded_by,"
                " detail, created_at)"
                " VALUES (?, ?, ?, ?, ?, ?, ?)",
                (aid, student_id, str(date),
                 status, str(recorded_by),
                 str(detail), now))
        notified = False
        if (status == "AUSENTE"
                and self._alerts is not None):
            self._alerts.publish(
                student_id=student_id,
                alert_type="ABSENCE",
                title="No se registra ingreso"
                      " del estudiante hoy",
                detail="Fecha " + str(date),
                recipient_role="PARENT")
            notified = True
        out = self.get(aid)
        out["parent_notified"] = notified
        return out

    def get(self, attendance_id
            ) -> Optional[dict]:
        row = self._db.query_one(
            "SELECT * FROM sm_attendance WHERE"
            " attendance_id = ?",
            (attendance_id,))
        if not row:
            return None
        return {"attendance_id":
                    str(row["attendance_id"]),
                "student_id":
                    str(row["student_id"]),
                "date": str(row["date"]),
                "status": str(row["status"]),
                "recorded_by":
                    str(row["recorded_by"]),
                "detail": str(row["detail"])}

    def rate(self, student_id,
             since_date="") -> dict:
        if since_date:
            rows = self._db.query_all(
                "SELECT status FROM"
                " sm_attendance WHERE"
                " student_id = ? AND date >= ?",
                (student_id, since_date))
        else:
            rows = self._db.query_all(
                "SELECT status FROM"
                " sm_attendance WHERE"
                " student_id = ?", (student_id,))
        total = len(rows)
        if total == 0:
            return {"total": 0,
                    "present": 0,
                    "present_rate_pct": 0.0}
        present = sum(1 for r in rows
                      if str(r["status"])
                      in ("PRESENTE",
                          "TARDANZA",
                          "JUSTIFICADO"))
        return {"total": total,
                "present": present,
                "present_rate_pct":
                    round(present * 100.0
                          / total, 2)}
