
"""Audit Compliance - NEXO / ZYRA (persistente)."""
from __future__ import annotations
from typing import Dict, List, Optional
import uuid
import json as _j
from shared_engines.common.clocks import Clock
from shared_engines.storage.database import Database
from shared_engines.storage.migrations import (
    Migration, MigrationRunner)

_MIGRATIONS = (
    Migration(1, "compliance_audits", (
        "CREATE TABLE IF NOT EXISTS compliance_audits (audit_id TEXT PRIMARY KEY, scope_json TEXT NOT NULL, findings_json TEXT NOT NULL DEFAULT '[]', observations_json TEXT NOT NULL DEFAULT '[]', violations_json TEXT NOT NULL DEFAULT '[]', risk_level TEXT NOT NULL DEFAULT 'LOW', status TEXT NOT NULL DEFAULT 'COMPLETED', audit_date REAL NOT NULL)",
    )),
)

class AuditComplianceEngine:
    """Auditoria de cumplimiento."""

    def __init__(self, db, clock):
        self._db = db
        self._clock = clock
        MigrationRunner(db, "nexo.complianceaudit", _MIGRATIONS).run(clock)

    def execute_audit(self, *, audit_scope):
        audit_id = f"AUD-{uuid.uuid4()}"
        now = self._clock.now()
        with self._db.transaction() as cursor:
            cursor.execute(
                "INSERT INTO compliance_audits"
                " (audit_id, scope_json, findings_json, observations_json, violations_json, risk_level, status, audit_date)"
                " VALUES (?, ?, '[]', '[]', '[]', 'LOW', 'COMPLETED', ?)",
                (audit_id, _j.dumps(audit_scope, default=str), now))
        return {"audit_id": audit_id, "audit_scope": audit_scope,
                "findings": [], "observations": [], "violations": [],
                "risk_level": "LOW", "status": "COMPLETED",
                "audit_date": now}

    def _load(self, audit_id):
        row = self._db.query_one(
            "SELECT * FROM compliance_audits WHERE audit_id = ?",
            (audit_id,))
        if not row:
            return None
        return {"audit_id": str(row["audit_id"]),
                "audit_scope": _j.loads(str(row["scope_json"])),
                "findings": _j.loads(str(row["findings_json"])),
                "observations": _j.loads(str(row["observations_json"])),
                "violations": _j.loads(str(row["violations_json"])),
                "risk_level": str(row["risk_level"]),
                "status": str(row["status"]),
                "audit_date": float(row["audit_date"])}

    def _save(self, audit):
        self._db.execute(
            "UPDATE compliance_audits SET findings_json = ?,"
            " observations_json = ?, violations_json = ?,"
            " risk_level = ? WHERE audit_id = ?",
            (_j.dumps(audit["findings"], default=str),
             _j.dumps(audit["observations"], default=str),
             _j.dumps(audit["violations"], default=str),
             audit["risk_level"], audit["audit_id"]))

    def add_finding(self, audit_id, finding):
        audit = self._load(audit_id)
        if not audit:
            return None
        audit["findings"].append(finding)
        self._save(audit)
        return audit

    def add_observation(self, audit_id, observation):
        audit = self._load(audit_id)
        if not audit:
            return None
        audit["observations"].append({
            "created_at": self._clock.now(),
            "message": observation})
        self._save(audit)
        return audit

    def add_violation(self, audit_id, violation):
        audit = self._load(audit_id)
        if not audit:
            return None
        audit["violations"].append(violation)
        n = len(audit["violations"])
        if n >= 10:
            audit["risk_level"] = "CRITICAL"
        elif n >= 5:
            audit["risk_level"] = "HIGH"
        elif n >= 2:
            audit["risk_level"] = "MEDIUM"
        self._save(audit)
        return audit

    def audit_summary(self, audit_id):
        audit = self._load(audit_id)
        if not audit:
            return None
        return {"audit_id": audit["audit_id"],
                "scope": audit["audit_scope"],
                "findings": len(audit["findings"]),
                "observations": len(audit["observations"]),
                "violations": len(audit["violations"]),
                "risk_level": audit["risk_level"],
                "status": audit["status"]}

    def generate_report(self, audit_id):
        audit = self._load(audit_id)
        if not audit:
            return None
        return {"audit": audit,
                "report_type": "COMPLIANCE_AUDIT_REPORT",
                "generated_at": self._clock.now()}
