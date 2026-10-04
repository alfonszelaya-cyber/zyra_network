
from __future__ import annotations
from apps.nexo.domain.risk.compliance_risk_engine import ComplianceRiskEngine

class MonitorComplianceRiskUseCase:
    def __init__(self, compliance_risk_engine):
        self._engine = compliance_risk_engine

    def execute(self, *, compliance_context):
        monitoring = self._engine.evaluate(
            compliance_record=compliance_context.get("compliance_record", {}),
            sanctions_result=compliance_context.get("sanctions_result", {}))
        return {"monitoring": monitoring, "status": "MONITORED"}
