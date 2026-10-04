
from __future__ import annotations
from apps.nexo.domain.risk.fraud_detection_engine import FraudDetectionEngine

class DetectFraudUseCase:
    def __init__(self, fraud_detection_engine):
        self._engine = fraud_detection_engine

    def execute(self, *, transaction_data):
        result = self._engine.detect(
            client_data=transaction_data.get("client_data", {}),
            accounting_data=transaction_data.get("accounting_data", {}),
            operations_data=transaction_data.get("operations_data", {}))
        return {"fraud_analysis": result, "status": "ANALYZED"}
