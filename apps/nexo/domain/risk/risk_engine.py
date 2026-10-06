
"""Risk Engine - NEXO / ZYRA."""
from __future__ import annotations
from datetime import datetime, timezone
from typing import Dict, List
import uuid

class RiskEngine:
    def __init__(self):
        self._history = []

    def evaluate(self, *, risk_components):
        scores = [c.get("score", 0) for c in risk_components.values() if isinstance(c, dict)]
        gs = round(sum(scores) / len(scores), 2) if scores else 0
        level = "CRITICAL" if gs >= 80 else ("HIGH" if gs >= 60 else ("MEDIUM" if gs >= 30 else "LOW"))
        r = {"risk_id": f"RISK-{uuid.uuid4()}", "score": gs, "level": level,
             "components": risk_components,
             "generated_at": datetime.now(timezone.utc).isoformat(), "status": "COMPLETED"}
        self._history.append(r)
        return r
