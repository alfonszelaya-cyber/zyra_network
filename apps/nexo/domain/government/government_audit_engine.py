
"""Government Audit Engine - auditorias de procesos
publicos (NG6). Auditorias con hallazgos por
severidad, cierre. Persistente."""
from __future__ import annotations
from typing import List, Optional
import json as _j
import uuid
from shared_engines.common.clocks import Clock
from shared_engines.storage.database import Database
from shared_engines.storage.migrations import (
    Migration, MigrationRunner)

SEVERITIES = ("LOW", "MEDIUM", "HIGH", "CRITICAL")

_MIGRATIONS = (
    Migration(1, "nexo_gov_audits", (
        "CREATE TABLE IF NOT EXISTS nexo_gov_audits (audit_id TEXT PRIMARY KEY, target_institution TEXT NOT NULL, process_ref TEXT NOT NULL DEFAULT '', scope TEXT NOT NULL DEFAULT '', status TEXT NOT NULL DEFAULT 'OPEN', findings_json TEXT NOT NULL DEFAULT '[]', closed_at REAL, created_at REAL NOT NULL)",
    )),
)

class GovernmentAuditEngine:
    """Auditorias gubernamentales con hallazgos."""

    def __init__(self, db, clock):
        self._db = db
        self._clock = clock
        MigrationRunner(db, "nexo.govaudit",
                        _MIGRATIONS).run(clock)

    def start_audit(self, *, target_institution,
                    process_ref="",
                    scope="") -> dict:
        aid = "GAUD-" + str(uuid.uuid4())
        now = self._clock.now()
        with self._db.transaction() as cursor:
            cursor.execute(
                "INSERT INTO nexo_gov_audits"
                " (audit_id, target_institution,"
                " process_ref, scope, status,"
                " findings_json, closed_at,"
                " created_at)"
                " VALUES (?, ?, ?, ?, 'OPEN', '[]',"
                " NULL, ?)",
                (aid, target_institution,
                 process_ref, scope, now))
        return self.get_audit(aid)

    def add_finding(self, *, audit_id, severity,
                    detail) -> dict:
        if severity not in SEVERITIES:
            severity = "MEDIUM"
        row = self._db.query_one(
            "SELECT status, findings_json FROM"
            " nexo_gov_audits WHERE audit_id = ?",
            (audit_id,))
        if not row:
            raise KeyError(audit_id)
        if str(row["status"]) != "OPEN":
            raise ValueError(
                "auditoria cerrada")
        findings = _j.loads(
            str(row["findings_json"]))
        findings.append({"severity": severity,
                         "detail": detail})
        self._db.execute(
            "UPDATE nexo_gov_audits SET"
            " findings_json = ? WHERE audit_id = ?",
            (_j.dumps(findings, default=str),
             audit_id))
        return self.get_audit(audit_id)

    def close_audit(self, audit_id) -> dict:
        row = self._db.query_one(
            "SELECT status FROM nexo_gov_audits"
            " WHERE audit_id = ?", (audit_id,))
        if not row:
            raise KeyError(audit_id)
        if str(row["status"]) != "OPEN":
            raise ValueError("ya cerrada")
        self._db.execute(
            "UPDATE nexo_gov_audits SET"
            " status = 'CLOSED', closed_at = ?"
            " WHERE audit_id = ?",
            (self._clock.now(), audit_id))
        return self.get_audit(audit_id)

    def get_audit(self,
                  audit_id) -> Optional[dict]:
        row = self._db.query_one(
            "SELECT * FROM nexo_gov_audits WHERE"
            " audit_id = ?", (audit_id,))
        if not row:
            return None
        findings = _j.loads(
            str(row["findings_json"]))
        return {"audit_id": str(row["audit_id"]),
                "target_institution":
                    str(row["target_institution"]),
                "process_ref":
                    str(row["process_ref"]),
                "scope": str(row["scope"]),
                "status": str(row["status"]),
                "findings": findings,
                "created_at":
                    float(row["created_at"])}

    def audits_of(self,
                  institution_id) -> List[dict]:
        rows = self._db.query_all(
            "SELECT audit_id FROM"
            " nexo_gov_audits WHERE"
            " target_institution = ?"
            " ORDER BY created_at",
            (institution_id,))
        return [self.get_audit(
            str(r["audit_id"]))
            for r in rows]

    def open_of(self, institution_id) -> List[dict]:
        rows = self._db.query_all(
            "SELECT audit_id FROM nexo_gov_audits"
            " WHERE target_institution = ? AND"
            " status = 'OPEN'", (institution_id,))
        return [self.get_audit(
            str(r["audit_id"]))
            for r in rows]
