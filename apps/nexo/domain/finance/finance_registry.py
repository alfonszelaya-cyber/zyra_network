
"""Finance Registry - registro de eventos financieros
(NG4). Persistente."""
from __future__ import annotations
from typing import List
import json as _j
import uuid
from shared_engines.common.clocks import Clock
from shared_engines.storage.database import Database
from shared_engines.storage.migrations import (
    Migration, MigrationRunner)

_MIGRATIONS = (
    Migration(1, "nexo_finance_registry", (
        "CREATE TABLE IF NOT EXISTS nexo_finance_registry (registry_id TEXT PRIMARY KEY, company_id TEXT NOT NULL, event_type TEXT NOT NULL, payload_json TEXT NOT NULL DEFAULT '{}', actor TEXT NOT NULL DEFAULT '', created_at REAL NOT NULL)",
    )),
)

class FinanceRegistry:
    """Registro de eventos financieros."""

    def __init__(self, db, clock):
        self._db = db
        self._clock = clock
        MigrationRunner(db, "nexo.finreg",
                        _MIGRATIONS).run(clock)

    def log_event(self, *, company_id, event_type,
                  payload=None, actor="") -> dict:
        rid = "FREG-" + str(uuid.uuid4())
        now = self._clock.now()
        with self._db.transaction() as cursor:
            cursor.execute(
                "INSERT INTO"
                " nexo_finance_registry"
                " (registry_id, company_id,"
                " event_type, payload_json, actor,"
                " created_at)"
                " VALUES (?, ?, ?, ?, ?, ?)",
                (rid, company_id, event_type,
                 _j.dumps(payload or {},
                          default=str), actor,
                 now))
        return {"registry_id": rid,
                "event_type": event_type,
                "created_at": now}

    def events_of(self, company_id,
                  limit=200) -> List[dict]:
        rows = self._db.query_all(
            "SELECT * FROM nexo_finance_registry"
            " WHERE company_id = ?"
            " ORDER BY created_at DESC LIMIT ?",
            (company_id, limit))
        return [{"registry_id":
                     str(r["registry_id"]),
                 "event_type":
                     str(r["event_type"]),
                 "payload": _j.loads(
                     str(r["payload_json"])),
                 "actor": str(r["actor"]),
                 "created_at":
                     float(r["created_at"])}
                for r in rows]
