
from __future__ import annotations
from apps.nexo.domain.risk.risk_evaluation_engine import RiskEvaluationEngine

class EvaluateRiskUseCase:
    def __init__(self, risk_evaluation_engine):
        self._engine = risk_evaluation_engine

    def execute(self, *, risk_context):
        evaluation = self._engine.evaluate(risk_context=risk_context)
        return {"evaluation": evaluation, "status": "COMPLETED"}
