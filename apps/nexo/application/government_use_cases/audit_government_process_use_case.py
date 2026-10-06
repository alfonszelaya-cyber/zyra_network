
from __future__ import annotations

class AuditGovernmentProcessUseCase:
    """Inicia auditoria y agrega hallazgo inicial."""

    def __init__(self, audit_engine):
        self._eng = audit_engine

    def execute(self, *, target_institution,
                process_ref, scope,
                finding_severity="",
                finding_detail="") -> dict:
        a = self._eng.start_audit(
            target_institution=target_institution,
            process_ref=process_ref,
            scope=scope)
        if finding_detail:
            a = self._eng.add_finding(
                audit_id=a["audit_id"],
                severity=(finding_severity
                          or "MEDIUM"),
                detail=finding_detail)
        return a
