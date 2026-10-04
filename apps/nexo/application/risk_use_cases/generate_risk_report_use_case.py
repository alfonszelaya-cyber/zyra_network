
from __future__ import annotations
from apps.nexo.domain.risk.risk_reporting_engine import RiskReportingEngine

class GenerateRiskReportUseCase:
    def __init__(self, risk_reporting_engine):
        self._engine = risk_reporting_engine

    def execute(self, *, period, filters=None):
        report = self._engine.generate_report(period=period, filters=filters or {})
        return {"period": period, "report": report, "status": "GENERATED"}
