
"""Compliance Registry - NEXO / ZYRA."""
from __future__ import annotations
from typing import Dict, List, Optional
import uuid
from shared_engines.common.clocks import Clock
from shared_engines.storage.database import Database
from shared_engines.storage.migrations import (
    Migration, MigrationRunner)

_MIGRATIONS = (
    Migration(1, "compliance_registry", (
        "CREATE TABLE IF NOT EXISTS compliance_registry (event_id TEXT PRIMARY KEY, company_id TEXT NOT NULL, event_type TEXT NOT NULL, description TEXT NOT NULL DEFAULT '', period_id TEXT, created_at REAL NOT NULL)",
    )),
)

class ComplianceRegistry:
    """Registro central de cumplimiento."""

    def __init__(self, db, clock):
        self._db = db
        self._clock = clock
        MigrationRunner(db, "nexo.compliancereg", _MIGRATIONS).run(clock)

    def store(self, event):
        event_id = event.get("event_id", f"CMP-{uuid.uuid4()}")
        now = self._clock.now()
        with self._db.transaction() as cursor:
            cursor.execute(
                "INSERT OR REPLACE INTO compliance_registry"
                " (event_id, company_id, event_type, description, period_id, created_at)"
                " VALUES (?, ?, ?, ?, ?, ?)",
                (event_id, str(event.get("company_id", "")),
                 str(event.get("event_type", "")),
                 str(event.get("description", "")),
                 event.get("period_id"), now))
        event["event_id"] = event_id
        event["created_at"] = now
        return event

    def get_by_period(self, *, company_id, period_id):
        rows = self._db.query_all(
            "SELECT * FROM compliance_registry"
            " WHERE company_id = ? AND period_id = ?"
            " ORDER BY created_at",
            (company_id, period_id))
        return [dict(r) for r in rows]

    def get_all(self):
        return [dict(r) for r in self._db.query_all(
            "SELECT * FROM compliance_registry ORDER BY created_at")]

    def total(self):
        row = self._db.query_one(
            "SELECT COUNT(*) AS n FROM compliance_registry")
        return int(row["n"]) if row else 0
