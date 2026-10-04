
from __future__ import annotations
from apps.nexo.domain.risk.financial_risk_engine import FinancialRiskEngine

class MonitorFinancialRiskUseCase:
    def __init__(self, financial_risk_engine):
        self._engine = financial_risk_engine

    def execute(self, *, financial_context):
        monitoring = self._engine.evaluate(
            accounting_data=financial_context.get("accounting_data", {}),
            finance_data=financial_context.get("finance_data", {}))
        return {"monitoring": monitoring, "status": "MONITORED"}
