
"""Compliance Reporting - NEXO / ZYRA (persistente)."""
from __future__ import annotations
from typing import Dict, List
import uuid
import json as _j
from shared_engines.common.clocks import Clock
from shared_engines.storage.database import Database
from shared_engines.storage.migrations import (
    Migration, MigrationRunner)

_MIGRATIONS = (
    Migration(1, "compliance_reports", (
        "CREATE TABLE IF NOT EXISTS compliance_reports (report_id TEXT PRIMARY KEY, report_type TEXT NOT NULL, data_json TEXT NOT NULL, generated_at REAL NOT NULL)",
    )),
)

class ComplianceReportingEngine:
    """Reportes de cumplimiento."""

    def __init__(self, db, clock):
        self._db = db
        self._clock = clock
        MigrationRunner(db, "nexo.compliancerep", _MIGRATIONS).run(clock)

    def generate_report(self, *, report_data, report_type="COMPLIANCE"):
        report_id = f"REP-{uuid.uuid4()}"
        now = self._clock.now()
        with self._db.transaction() as cursor:
            cursor.execute(
                "INSERT INTO compliance_reports"
                " (report_id, report_type, data_json, generated_at)"
                " VALUES (?, ?, ?, ?)",
                (report_id, report_type,
                 _j.dumps(report_data, default=str), now))
        return {"report_id": report_id, "generated_at": now,
                "report_type": report_type, "data": report_data,
                "status": "GENERATED"}

    def generate_executive_report(self, *, events, alerts, violations):
        return self.generate_report(
            report_data={"events": len(events),
                         "alerts": len(alerts),
                         "violations": len(violations)},
            report_type="EXECUTIVE_COMPLIANCE")

    def get_reports(self):
        rows = self._db.query_all(
            "SELECT * FROM compliance_reports ORDER BY generated_at")
        return [{"report_id": str(r["report_id"]),
                 "report_type": str(r["report_type"]),
                 "data": _j.loads(str(r["data_json"])),
                 "generated_at": float(r["generated_at"])}
                for r in rows]

    def generate_summary(self):
        return {"reports": len(self.get_reports()),
                "generated_at": self._clock.now()}
