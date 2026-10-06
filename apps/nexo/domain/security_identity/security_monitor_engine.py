
"""Nexo Security Monitor - eventos de seguridad (NG8)."""
from __future__ import annotations
from typing import Dict, List
import uuid
from shared_engines.common.clocks import Clock
from shared_engines.storage.database import Database
from shared_engines.storage.migrations import (
    Migration, MigrationRunner)

SEVERITIES = ("INFO", "LOW", "MEDIUM", "HIGH",
              "CRITICAL")

_MIGRATIONS = (
    Migration(1, "nexo_security_events", (
        "CREATE TABLE IF NOT EXISTS nexo_security_events (event_id TEXT PRIMARY KEY, event_type TEXT NOT NULL, actor TEXT NOT NULL DEFAULT '', severity TEXT NOT NULL DEFAULT 'INFO', detail TEXT NOT NULL DEFAULT '', created_at REAL NOT NULL)",
    )),
)

class NexoSecurityMonitor:
    """Eventos de seguridad NEXO."""

    def __init__(self, db, clock):
        self._db = db
        self._clock = clock
        MigrationRunner(db, "nexo.secmon",
                        _MIGRATIONS).run(clock)

    def log_event(self, *, event_type, actor="",
                  severity="INFO",
                  detail="") -> dict:
        if severity not in SEVERITIES:
            severity = "INFO"
        eid = "SEC-" + str(uuid.uuid4())
        now = self._clock.now()
        with self._db.transaction() as cursor:
            cursor.execute(
                "INSERT INTO nexo_security_events"
                " (event_id, event_type, actor,"
                " severity, detail, created_at)"
                " VALUES (?, ?, ?, ?, ?, ?)",
                (eid, event_type, actor,
                 severity, detail, now))
        return {"event_id": eid,
                "event_type": event_type,
                "actor": actor,
                "severity": severity}

    def recent(self, limit=50) -> List[dict]:
        rows = self._db.query_all(
            "SELECT * FROM nexo_security_events"
            " ORDER BY created_at DESC LIMIT ?",
            (limit,))
        return [{"event_id": str(r["event_id"]),
                 "event_type": str(r["event_type"]),
                 "actor": str(r["actor"]),
                 "severity": str(r["severity"]),
                 "detail": str(r["detail"]),
                 "created_at":
                     float(r["created_at"])}
                for r in rows]

    def counts_by_type(self) -> Dict[str, int]:
        rows = self._db.query_all(
            "SELECT event_type, COUNT(*) AS c"
            " FROM nexo_security_events"
            " GROUP BY event_type")
        return {str(r["event_type"]): int(r["c"])
                for r in rows}
