
from __future__ import annotations
from apps.nexo.domain.risk.risk_scoring_engine import RiskScoringEngine

class CalculateRiskScoreUseCase:
    def __init__(self, risk_scoring_engine):
        self._engine = risk_scoring_engine

    def execute(self, *, entity_data):
        zero = {"score": 0}
        r = self._engine.calculate(
            compliance_risk=entity_data.get("compliance_risk", zero),
            financial_risk=entity_data.get("financial_risk", zero),
            operational_risk=entity_data.get("operational_risk", zero),
            geopolitical_risk=entity_data.get("geopolitical_risk", zero),
            fraud_risk=entity_data.get("fraud_risk", zero),
            supply_chain_risk=entity_data.get("supply_chain_risk", zero),
            sanctions_risk=entity_data.get("sanctions_risk", zero),
            war_risk=entity_data.get("war_risk", zero))
        return {"risk_score": r["global_score"], "risk_level": r["risk_level"],
                "status": "CALCULATED"}
