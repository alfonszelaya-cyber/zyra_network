
"""Emotional Monitoring (SM4). Orden rowid:
determinista con reloj congelado."""
from __future__ import annotations
from typing import List, Optional
import uuid
from shared_engines.common.clocks import Clock
from shared_engines.storage.database import (
    Database)
from shared_engines.storage.migrations import (
    Migration, MigrationRunner)

NORMAL_MOODS = ("feliz", "tranquilo", "motivado",
                "contento")
ALERT_MOODS = ("triste", "estresado", "frustrado",
               "enojado", "ansioso", "cansado")
CRISIS = "crisis"

_MIGRATIONS = (
    Migration(1, "sm_emotional", (
        "CREATE TABLE IF NOT EXISTS sm_emotional (record_id TEXT PRIMARY KEY, student_id TEXT NOT NULL, mood TEXT NOT NULL, level TEXT NOT NULL, detail TEXT NOT NULL DEFAULT '', created_at REAL NOT NULL)",
    )),
)

class EmotionalMonitoringEngine:
    """Monitoreo emocional del estudiante."""

    def __init__(self, db, clock,
                 alert_engine=None):
        self._db = db
        self._clock = clock
        self._alerts = alert_engine
        MigrationRunner(db, "sm.emotional",
                        _MIGRATIONS).run(clock)

    def _classify(self, mood) -> str:
        m = str(mood).strip().lower()
        if m == CRISIS:
            return "CRITICAL"
        if m in NORMAL_MOODS:
            return "NORMAL"
        if m in ALERT_MOODS:
            return "ALERT"
        raise ValueError(
            "mood no reconocido: " + str(mood))

    def _escalated(self, cursor,
                   student_id) -> bool:
        rows = cursor.execute(
            "SELECT level FROM sm_emotional"
            " WHERE student_id = ? ORDER BY"
            " rowid DESC LIMIT 4",
            (student_id,)).fetchall()
        alerts = sum(1 for r in rows
                     if str(r["level"])
                     == "ALERT")
        return alerts >= 3

    def record_mood(self, *, student_id, mood,
                    detail="") -> dict:
        base = self._classify(mood)
        rid = "SMEMO-" + str(uuid.uuid4())
        now = self._clock.now()
        level = base
        escalated = False
        with self._db.transaction() as cursor:
            cursor.execute(
                "INSERT INTO sm_emotional"
                " (record_id, student_id, mood,"
                " level, detail, created_at)"
                " VALUES (?, ?, ?, ?, ?, ?)",
                (rid, student_id,
                 str(mood).strip().lower(),
                 level, str(detail), now))
            if base == "ALERT":
                if self._escalated(cursor,
                                   student_id):
                    level = "CRITICAL"
                    escalated = True
                    cursor.execute(
                        "UPDATE sm_emotional SET"
                        " level = 'CRITICAL' WHERE"
                        " record_id = ?", (rid,))
        notified = False
        if (self._alerts is not None
                and level != "NORMAL"):
            self._alerts.publish(
                student_id=student_id,
                alert_type=("HEALTH" if level
                            == "CRITICAL"
                            else "GENERAL"),
                title=("Alerta emocional critica"
                       if level == "CRITICAL"
                       else "Seguimiento"
                            " emocional"),
                detail=("estado reportado: "
                        + str(mood)),
                recipient_role="PARENT")
            notified = True
        return {"record_id": rid,
                "mood": str(mood).strip().lower(),
                "level": level,
                "escalated": escalated,
                "parent_notified": notified}

    def emotional_state(self, student_id
                        ) -> dict:
        rows = self._db.query_all(
            "SELECT * FROM sm_emotional WHERE"
            " student_id = ? ORDER BY"
            " rowid DESC LIMIT 10",
            (student_id,))
        records = [{"mood": str(r["mood"]),
                    "level": str(r["level"]),
                    "created_at": float(
                        r["created_at"])}
                   for r in rows]
        current = ("NORMAL" if not records
                   else records[0]["level"])
        alerts = sum(1 for r in records
                     if r["level"] != "NORMAL")
        return {"student_id": student_id,
                "current_level": current,
                "recent_alerts": alerts,
                "records": records}

    def history_of(self, student_id
                   ) -> List[dict]:
        rows = self._db.query_all(
            "SELECT * FROM sm_emotional WHERE"
            " student_id = ? ORDER BY rowid ASC",
            (student_id,))
        return [{"mood": str(r["mood"]),
                 "level": str(r["level"]),
                 "detail": str(r["detail"]),
                 "created_at":
                     float(r["created_at"])}
                for r in rows]
