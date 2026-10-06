
"""Calendar Engine - calendario escolar (SM4).
Examenes proximos -> alerta EXAM_UPCOMING."""
from __future__ import annotations
from typing import List
import uuid
from shared_engines.common.clocks import Clock
from shared_engines.storage.database import (
    Database)
from shared_engines.storage.migrations import (
    Migration, MigrationRunner)

EVENT_TYPES = ("EXAM", "HOLIDAY", "MEETING",
               "ASSIGNMENT", "TERM_START",
               "TERM_END")

_MIGRATIONS = (
    Migration(1, "sm_calendar", (
        "CREATE TABLE IF NOT EXISTS sm_calendar (event_id TEXT PRIMARY KEY, date TEXT NOT NULL, event_type TEXT NOT NULL, title TEXT NOT NULL, subject TEXT NOT NULL DEFAULT '', created_at REAL NOT NULL)",
    )),
)

class CalendarEngine:
    """Calendario escolar (persistente)."""

    def __init__(self, db, clock,
                 alert_engine=None):
        self._db = db
        self._clock = clock
        self._alerts = alert_engine
        MigrationRunner(db, "sm.calendar",
                        _MIGRATIONS).run(clock)

    def add_event(self, *, date, event_type,
                  title, subject="") -> dict:
        if event_type not in EVENT_TYPES:
            raise ValueError(
                "event_type invalido: "
                + str(event_type))
        if not str(date).strip():
            raise ValueError("date requerida")
        if not str(title).strip():
            raise ValueError("title requerido")
        eid = "SMCAL-" + str(uuid.uuid4())
        now = self._clock.now()
        with self._db.transaction() as cursor:
            cursor.execute(
                "INSERT INTO sm_calendar"
                " (event_id, date, event_type,"
                " title, subject, created_at)"
                " VALUES (?, ?, ?, ?, ?, ?)",
                (eid, str(date), event_type,
                 str(title).strip(),
                 str(subject), now))
        return {"event_id": eid,
                "date": str(date),
                "event_type": event_type,
                "title": str(title).strip()}

    def upcoming(self, *, from_date,
                 days=7) -> List[dict]:
        end = self._plus_days(from_date, days)
        rows = self._db.query_all(
            "SELECT * FROM sm_calendar WHERE"
            " date >= ? AND date <= ?"
            " ORDER BY date",
            (str(from_date), end))
        return [{"event_id":
                     str(r["event_id"]),
                 "date": str(r["date"]),
                 "event_type":
                     str(r["event_type"]),
                 "title": str(r["title"]),
                 "subject": str(r["subject"])}
                for r in rows]

    def _plus_days(self, iso_date, days) -> str:
        import datetime
        d = datetime.date.fromisoformat(
            str(iso_date))
        return (d
                + datetime.timedelta(
                    days=int(days))
                ).isoformat()

    def publish_exam_alerts(self, *, from_date,
                            days=7) -> int:
        events = self.upcoming(
            from_date=from_date, days=days)
        count = 0
        for e in events:
            if (e["event_type"] == "EXAM"
                    and self._alerts
                    is not None):
                self._alerts.publish(
                    student_id="*",
                    alert_type="EXAM_UPCOMING",
                    title="Examen proximo: "
                          + e["title"],
                    detail=("fecha "
                            + e["date"]
                            + (" materia "
                               + e["subject"]
                               if e["subject"]
                               else "")),
                    recipient_role="PARENT")
                count = count + 1
        return count
