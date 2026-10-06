
"""Registry de auditoria NEXO: consultas agregadas."""
from __future__ import annotations
from typing import Dict
from shared_engines.common.clocks import Clock
from shared_engines.storage.database import Database

class NexoAuditRegistry:
    """Consultas agregadas sobre nexo_audit_events."""

    def __init__(self, db, clock):
        self._db = db
        self._clock = clock

    def counts_by_event(self) -> Dict[str, int]:
        rows = self._db.query_all(
            "SELECT event, COUNT(*) AS c FROM"
            " nexo_audit_events GROUP BY event")
        return {str(r["event"]): int(r["c"])
                for r in rows}

    def counts_by_actor(self) -> Dict[str, int]:
        rows = self._db.query_all(
            "SELECT actor, COUNT(*) AS c FROM"
            " nexo_audit_events GROUP BY actor")
        return {str(r["actor"]): int(r["c"])
                for r in rows}

    def last_for_entity(self, entity):
        row = self._db.query_one(
            "SELECT audit_id, event, created_at FROM"
            " nexo_audit_events WHERE entity = ?"
            " ORDER BY created_at DESC LIMIT 1",
            (entity,))
        if not row:
            return None
        return {"audit_id": str(row["audit_id"]),
                "event": str(row["event"]),
                "created_at": float(row["created_at"])}
