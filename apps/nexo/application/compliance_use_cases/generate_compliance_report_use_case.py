
from __future__ import annotations
from apps.nexo.domain.compliance.compliance_registry import ComplianceRegistry

class GenerateComplianceReportUseCase:
    def __init__(self, compliance_registry):
        self._engine = compliance_registry

    def execute(self, *, company_id, period_id):
        events = self._engine.get_by_period(company_id=company_id, period_id=period_id)
        return {"company_id": company_id, "period_id": period_id,
                "events": events, "total_events": len(events)}
