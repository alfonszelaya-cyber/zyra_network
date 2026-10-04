
"""Compliance Engine - NEXO / ZYRA (persistente)."""
from __future__ import annotations
from typing import Dict, List, Optional
import uuid
from shared_engines.common.clocks import Clock
from shared_engines.storage.database import Database
from shared_engines.storage.migrations import (
    Migration, MigrationRunner)

_MIGRATIONS = (
    Migration(1, "compliance_core", (
        "CREATE TABLE IF NOT EXISTS compliance_core (item_id TEXT PRIMARY KEY, item_kind TEXT NOT NULL, entity_id TEXT NOT NULL, payload_json TEXT NOT NULL, created_at REAL NOT NULL)",
    )),
)

class ComplianceEngine:
    """Motor central de cumplimiento."""

    def __init__(self, db, clock):
        self._db = db
        self._clock = clock
        MigrationRunner(db, "nexo.compliance", _MIGRATIONS).run(clock)

    def _insert(self, kind, entity_id, payload):
        import json as _j
        item_id = f"CMP-{uuid.uuid4()}"
        with self._db.transaction() as cursor:
            cursor.execute(
                "INSERT INTO compliance_core"
                " (item_id, item_kind, entity_id, payload_json, created_at)"
                " VALUES (?, ?, ?, ?, ?)",
                (item_id, kind, entity_id,
                 _j.dumps(payload, default=str),
                 self._clock.now()))
        return item_id

    def register_event(self, *, event_type, entity_id, details):
        item_id = self._insert("EVENT", entity_id,
                               {"event_type": event_type, **details})
        return {"event_id": item_id, "event_type": event_type,
                "entity_id": entity_id, "details": details,
                "status": "REGISTERED"}

    def register_violation(self, *, entity_id, violation_type, details):
        item_id = self._insert("VIOLATION", entity_id,
                               {"violation_type": violation_type, **details})
        return {"violation_id": item_id, "entity_id": entity_id,
                "violation_type": violation_type, "details": details,
                "status": "OPEN"}

    def create_alert(self, *, entity_id, level, message):
        item_id = self._insert("ALERT", entity_id,
                               {"level": level, "message": message})
        return {"alert_id": item_id, "entity_id": entity_id,
                "level": level, "message": message, "status": "ACTIVE"}

    def get_events_by_entity(self, entity_id):
        rows = self._db.query_all(
            "SELECT * FROM compliance_core"
            " WHERE entity_id = ? AND item_kind = 'EVENT'"
            " ORDER BY created_at", (entity_id,))
        return [dict(r) for r in rows]

    def generate_summary(self):
        rows = self._db.query_all(
            "SELECT item_kind, COUNT(*) AS n"
            " FROM compliance_core GROUP BY item_kind")
        counts = {str(r["item_kind"]): int(r["n"]) for r in rows}
        return {"events": counts.get("EVENT", 0),
                "violations": counts.get("VIOLATION", 0),
                "alerts": counts.get("ALERT", 0),
                "generated_at": self._clock.now()}

    def generate_report(self):
        return {"summary": self.generate_summary(),
                "report_type": "COMPLIANCE_REPORT",
                "generated_at": self._clock.now()}
