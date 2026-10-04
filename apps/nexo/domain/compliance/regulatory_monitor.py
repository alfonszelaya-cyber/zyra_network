
"""Regulatory Monitor - NEXO / ZYRA (persistente)."""
from __future__ import annotations
from typing import Dict, List
import uuid
from shared_engines.common.clocks import Clock
from shared_engines.storage.database import Database
from shared_engines.storage.migrations import (
    Migration, MigrationRunner)

_MIGRATIONS = (
    Migration(1, "regulatory_checks", (
        "CREATE TABLE IF NOT EXISTS regulatory_checks (check_id TEXT PRIMARY KEY, jurisdiction TEXT NOT NULL, checked_at REAL NOT NULL, status TEXT NOT NULL DEFAULT 'COMPLETED')",
    )),
    Migration(2, "regulatory_alerts", (
        "CREATE TABLE IF NOT EXISTS regulatory_alerts (alert_id TEXT PRIMARY KEY, jurisdiction TEXT NOT NULL, title TEXT NOT NULL, description TEXT NOT NULL DEFAULT '', severity TEXT NOT NULL DEFAULT 'MEDIUM', status TEXT NOT NULL DEFAULT 'OPEN', created_at REAL NOT NULL)",
    )),
)

class RegulatoryMonitor:
    """Monitoreo regulatorio."""

    def __init__(self, db, clock):
        self._db = db
        self._clock = clock
        MigrationRunner(db, "nexo.regmonitor", _MIGRATIONS).run(clock)

    def monitor(self, *, jurisdiction):
        check_id = f"REG-{uuid.uuid4()}"
        now = self._clock.now()
        with self._db.transaction() as cursor:
            cursor.execute(
                "INSERT INTO regulatory_checks"
                " (check_id, jurisdiction, checked_at, status)"
                " VALUES (?, ?, ?, 'COMPLETED')",
                (check_id, jurisdiction, now))
        return {"check_id": check_id, "jurisdiction": jurisdiction,
                "checked_at": now, "changes_detected": False,
                "status": "COMPLETED"}

    def register_change(self, *, jurisdiction, title,
                        description, severity="MEDIUM"):
        alert_id = f"ALT-{uuid.uuid4()}"
        now = self._clock.now()
        with self._db.transaction() as cursor:
            cursor.execute(
                "INSERT INTO regulatory_alerts"
                " (alert_id, jurisdiction, title, description, severity, status, created_at)"
                " VALUES (?, ?, ?, ?, ?, 'OPEN', ?)",
                (alert_id, jurisdiction, title, description,
                 severity, now))
        return {"alert_id": alert_id, "jurisdiction": jurisdiction,
                "title": title, "severity": severity, "status": "OPEN"}

    def get_alerts_by_jurisdiction(self, jurisdiction):
        rows = self._db.query_all(
            "SELECT * FROM regulatory_alerts"
            " WHERE jurisdiction = ? ORDER BY created_at",
            (jurisdiction,))
        return [dict(r) for r in rows]

    def generate_summary(self):
        c = self._db.query_one("SELECT COUNT(*) AS n FROM regulatory_checks")
        a = self._db.query_one("SELECT COUNT(*) AS n FROM regulatory_alerts")
        return {"checks": int(c["n"]) if c else 0,
                "alerts": int(a["n"]) if a else 0,
                "generated_at": self._clock.now()}

    def generate_report(self):
        return {"checks": self._db.query_all("SELECT * FROM regulatory_checks"),
                "alerts": self._db.query_all("SELECT * FROM regulatory_alerts"),
                "report_type": "REGULATORY_MONITOR",
                "generated_at": self._clock.now()}
