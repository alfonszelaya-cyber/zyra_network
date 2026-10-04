
from __future__ import annotations
from apps.nexo.domain.risk.operational_risk_engine import OperationalRiskEngine

class MonitorOperationalRiskUseCase:
    def __init__(self, operational_risk_engine):
        self._engine = operational_risk_engine

    def execute(self, *, operational_context):
        monitoring = self._engine.evaluate(
            logistics_data=operational_context.get("logistics_data", {}),
            operations_data=operational_context.get("operations_data", {}))
        return {"monitoring": monitoring, "status": "MONITORED", "risk_type": "OPERATIONAL"}
