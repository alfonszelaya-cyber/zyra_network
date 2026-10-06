
"""Risk Scoring - NEXO / ZYRA."""
from __future__ import annotations
from datetime import datetime, timezone
from typing import Dict
import uuid

class RiskScoringEngine:
    def __init__(self):
        self._history = []

    def calculate(self, *, compliance_risk, financial_risk, operational_risk,
                  geopolitical_risk, fraud_risk, supply_chain_risk,
                  sanctions_risk, war_risk):
        scores = [compliance_risk.get("score", 0), financial_risk.get("score", 0),
                  operational_risk.get("score", 0), geopolitical_risk.get("score", 0),
                  fraud_risk.get("score", 0), supply_chain_risk.get("score", 0),
                  sanctions_risk.get("score", 0), war_risk.get("score", 0)]
        gs = round(sum(scores) / len(scores), 2)
        level = "CRITICAL" if gs >= 85 else ("HIGH" if gs >= 70 else ("MEDIUM" if gs >= 40 else "LOW"))
        r = {"score_id": f"RSK-{uuid.uuid4()}", "global_score": gs, "risk_level": level,
             "generated_at": datetime.now(timezone.utc).isoformat(), "status": "CALCULATED"}
        self._history.append(r)
        return r
