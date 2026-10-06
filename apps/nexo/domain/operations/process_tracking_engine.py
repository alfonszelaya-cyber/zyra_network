
"""Process Tracking Engine - NEXO / ZYRA (migrado
mejorado). Trazabilidad completa de procesos: cada
evento queda persistido (quien, que, cuando, detalle).
Evidencia auditable para Hacienda, bancos, alcaldias
y auditorias internas."""
from __future__ import annotations
from typing import List, Optional
import uuid
from shared_engines.common.clocks import Clock
from shared_engines.storage.database import Database
from shared_engines.storage.migrations import (
    Migration, MigrationRunner)

_MIGRATIONS = (
    Migration(1, "nexo_process_events", (
        "CREATE TABLE IF NOT EXISTS nexo_process_events (event_id TEXT PRIMARY KEY, process_id TEXT NOT NULL, event_type TEXT NOT NULL, actor TEXT NOT NULL DEFAULT '', detail TEXT NOT NULL DEFAULT '', created_at REAL NOT NULL)",
    )),
)

class ProcessTrackingEngine:
    """Trazabilidad de procesos (persistente)."""

    def __init__(self, db, clock):
        self._db = db
        self._clock = clock
        MigrationRunner(db, "nexo.proctrack",
                        _MIGRATIONS).run(clock)

    def append_event(self, *, process_id, event_type,
                     actor="", detail="") -> dict:
        eid = "EVT-" + str(uuid.uuid4())
        now = self._clock.now()
        with self._db.transaction() as cursor:
            cursor.execute(
                "INSERT INTO nexo_process_events"
                " (event_id, process_id, event_type,"
                " actor, detail, created_at)"
                " VALUES (?, ?, ?, ?, ?, ?)",
                (eid, process_id, event_type, actor,
                 detail, now))
        return {"event_id": eid,
                "process_id": process_id,
                "event_type": event_type,
                "actor": actor, "detail": detail,
                "created_at": now}

    def get_timeline(self, process_id) -> List[dict]:
        rows = self._db.query_all(
            "SELECT * FROM nexo_process_events"
            " WHERE process_id = ?"
            " ORDER BY created_at, event_id",
            (process_id,))
        return [{"event_id": str(r["event_id"]),
                 "event_type": str(r["event_type"]),
                 "actor": str(r["actor"]),
                 "detail": str(r["detail"]),
                 "created_at": float(r["created_at"])}
                for r in rows]

    def get_last_event(self,
                       process_id) -> Optional[dict]:
        tl = self.get_timeline(process_id)
        return tl[-1] if tl else None

    def event_count(self, process_id) -> int:
        row = self._db.query_one(
            "SELECT COUNT(*) AS c FROM"
            " nexo_process_events"
            " WHERE process_id = ?", (process_id,))
        return int(row["c"]) if row else 0
