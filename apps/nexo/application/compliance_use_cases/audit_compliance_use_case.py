
from __future__ import annotations
from apps.nexo.domain.compliance.audit_compliance_engine import AuditComplianceEngine

class AuditComplianceUseCase:
    def __init__(self, audit_engine):
        self._engine = audit_engine

    def execute(self, *, company_id, period_id):
        audit = self._engine.execute_audit(audit_scope={"company_id": company_id, "period_id": period_id})
        return {"company_id": company_id, "period_id": period_id,
                "audit_id": audit["audit_id"], "findings": audit["findings"],
                "total_findings": len(audit["findings"])}
