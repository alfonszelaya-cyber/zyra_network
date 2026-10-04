
"""Risk Evaluation - NEXO / ZYRA."""
from __future__ import annotations
from typing import Dict
import uuid
from datetime import datetime

class RiskEvaluationEngine:
    """Evalua contexto de riesgo."""

    def evaluate(self, *, risk_context):
        scores = []
        for v in risk_context.get("components", {}).values():
            if isinstance(v, dict):
                scores.append(v.get("score", 0))
        if not scores:
            scores = [int(risk_context.get("score", 0))]
        gs = round(sum(scores) / len(scores), 2)
        if gs >= 80:
            level = "CRITICAL"
        elif gs >= 60:
            level = "HIGH"
        elif gs >= 30:
            level = "MEDIUM"
        else:
            level = "LOW"
        return {"evaluation_id": f"EVL-{uuid.uuid4()}",
                "global_score": gs, "level": level,
                "components": risk_context.get("components", {}),
                "generated_at": datetime.utcnow().isoformat(),
                "status": "COMPLETED"}
