
# client_history_engine.py - NEXO / ZYRA (migrado mejorado)
from __future__ import annotations
from typing import List, Optional
import uuid
from shared_engines.common.clocks import Clock
from shared_engines.storage.database import Database
from shared_engines.storage.migrations import (
    Migration, MigrationRunner)

_MIGRATIONS = (
    Migration(1, "nexo_client_history", ("CREATE TABLE IF NOT EXISTS nexo_client_history (event_id TEXT PRIMARY KEY, client_id TEXT NOT NULL, event_type TEXT NOT NULL, details_json TEXT NOT NULL DEFAULT '{}', created_at REAL NOT NULL)",)),
)

class ClientHistoryEngine:
    """Motor de historial de clientes (persistente)."""

    def __init__(self, db: Database, clock: Clock) -> None:
        self._db = db
        self._clock = clock
        MigrationRunner(db, "nexo.clienthistory",
                        _MIGRATIONS).run(clock)

    def register_event(self, client_id: str,
                       event_type: str,
                       details: dict) -> dict:
        import json as _j
        event_id = f"HIS-{uuid.uuid4()}"
        now = self._clock.now()
        with self._db.transaction() as cursor:
            cursor.execute(
                "INSERT INTO nexo_client_history"
                " (event_id, client_id, event_type,"
                " details_json, created_at)"
                " VALUES (?, ?, ?, ?, ?)",
                (event_id, client_id, event_type,
                 _j.dumps(details, default=str), now))
        return {"event_id": event_id,
                "client_id": client_id,
                "event_type": event_type,
                "details": details,
                "created_at": now}

    def register_financial_event(self, client_id, details):
        return self.register_event(client_id, "FINANCIAL", details)

    def register_fiscal_event(self, client_id, details):
        return self.register_event(client_id, "FISCAL", details)

    def register_operational_event(self, client_id, details):
        return self.register_event(client_id, "OPERATIONAL", details)

    def register_risk_event(self, client_id, details):
        return self.register_event(client_id, "RISK", details)

    def register_compliance_event(self, client_id, details):
        return self.register_event(client_id, "COMPLIANCE", details)

    def register_audit_event(self, client_id, details):
        return self.register_event(client_id, "AUDIT", details)

    def get_client_history(self, client_id: str) -> List[dict]:
        import json as _j
        rows = self._db.query_all(
            "SELECT * FROM nexo_client_history"
            " WHERE client_id = ? ORDER BY created_at",
            (client_id,))
        return [{"event_id": str(r["event_id"]),
                 "client_id": str(r["client_id"]),
                 "event_type": str(r["event_type"]),
                 "details": _j.loads(
                     str(r["details_json"])),
                 "created_at": float(r["created_at"])}
                for r in rows]

    def get_events_by_type(self, client_id: str,
                           event_type: str) -> List[dict]:
        return [e for e in self.get_client_history(client_id)
                if e["event_type"] == event_type]

    def get_total_events(self, client_id: str) -> int:
        return len(self.get_client_history(client_id))

    def generate_timeline(self, client_id: str) -> List[dict]:
        return sorted(
            self.get_client_history(client_id),
            key=lambda x: x["created_at"],
            reverse=True)

    def generate_summary(self, client_id: str) -> dict:
        history = self.get_client_history(client_id)
        return {"client_id": client_id,
                "total_events": len(history),
                "financial_events": len(
                    self.get_events_by_type(
                        client_id, "FINANCIAL")),
                "fiscal_events": len(
                    self.get_events_by_type(
                        client_id, "FISCAL")),
                "operational_events": len(
                    self.get_events_by_type(
                        client_id, "OPERATIONAL")),
                "risk_events": len(
                    self.get_events_by_type(
                        client_id, "RISK")),
                "generated_at": self._clock.now()}
