
"""Sanctions Monitor - NEXO / ZYRA (informa, no bloquea)."""
from __future__ import annotations
from typing import Dict, List
import uuid
from shared_engines.common.clocks import Clock
from shared_engines.storage.database import Database
from shared_engines.storage.migrations import (
    Migration, MigrationRunner)

_MIGRATIONS = (
    Migration(1, "sanctions_verifications", (
        "CREATE TABLE IF NOT EXISTS sanctions_verifications (verification_id TEXT PRIMARY KEY, entity_name TEXT NOT NULL, list_source TEXT NOT NULL DEFAULT 'internal', sanctioned INTEGER NOT NULL DEFAULT 0, checked_at REAL NOT NULL)",
    )),
    Migration(2, "sanctions_alerts", (
        "CREATE TABLE IF NOT EXISTS sanctions_alerts (alert_id TEXT PRIMARY KEY, entity_name TEXT NOT NULL, reason TEXT NOT NULL, severity TEXT NOT NULL DEFAULT 'HIGH', status TEXT NOT NULL DEFAULT 'OPEN', created_at REAL NOT NULL)",
    )),
)

class SanctionsMonitor:
    """Monitoreo de sanciones (informa/bonifica)."""

    def __init__(self, db, clock, *, sanctioned_names=None):
        self._db = db
        self._clock = clock
        self._sanctioned = [n.upper() for n in (sanctioned_names or [])]
        MigrationRunner(db, "nexo.sanctions", _MIGRATIONS).run(clock)

    def verify(self, *, entity_name, list_source="internal"):
        vid = f"SAN-{uuid.uuid4()}"
        now = self._clock.now()
        sanctioned = entity_name.strip().upper() in self._sanctioned
        with self._db.transaction() as cursor:
            cursor.execute(
                "INSERT INTO sanctions_verifications"
                " (verification_id, entity_name, list_source, sanctioned, checked_at)"
                " VALUES (?, ?, ?, ?, ?)",
                (vid, entity_name, list_source,
                 1 if sanctioned else 0, now))
        return {"verification_id": vid, "entity_name": entity_name,
                "sanctioned": sanctioned, "list_source": list_source,
                "checked_at": now, "status": "VERIFIED"}

    def register_alert(self, *, entity_name, reason, severity="HIGH"):
        alert_id = f"ALT-{uuid.uuid4()}"
        now = self._clock.now()
        with self._db.transaction() as cursor:
            cursor.execute(
                "INSERT INTO sanctions_alerts"
                " (alert_id, entity_name, reason, severity, status, created_at)"
                " VALUES (?, ?, ?, ?, 'OPEN', ?)",
                (alert_id, entity_name, reason, severity, now))
        return {"alert_id": alert_id, "entity_name": entity_name,
                "reason": reason, "severity": severity, "status": "OPEN"}

    def get_entity_history(self, entity_name):
        rows = self._db.query_all(
            "SELECT * FROM sanctions_verifications"
            " WHERE entity_name = ? ORDER BY checked_at",
            (entity_name,))
        return [dict(r) for r in rows]

    def generate_summary(self):
        rows = self._db.query_all(
            "SELECT DISTINCT entity_name FROM sanctions_verifications"
            " WHERE sanctioned = 1")
        total = self._db.query_one(
            "SELECT COUNT(*) AS n FROM sanctions_verifications")
        alerts = self._db.query_one(
            "SELECT COUNT(*) AS n FROM sanctions_alerts")
        return {"verifications": int(total["n"]) if total else 0,
                "alerts": int(alerts["n"]) if alerts else 0,
                "sanctioned_entities": len(rows),
                "generated_at": self._clock.now()}

    def generate_report(self):
        return {"verifications": self._db.query_all(
                    "SELECT * FROM sanctions_verifications"),
                "alerts": self._db.query_all(
                    "SELECT * FROM sanctions_alerts"),
                "report_type": "SANCTIONS_MONITOR",
                "generated_at": self._clock.now()}
