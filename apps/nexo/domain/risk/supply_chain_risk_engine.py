
"""Supply Chain Risk - NEXO / ZYRA."""
from __future__ import annotations
from datetime import datetime, timezone
from typing import Dict, List
import uuid

class SupplyChainRiskEngine:
    def __init__(self):
        self._history = []

    def evaluate(self, *, logistics_data, supplier_data):
        score = 0
        score += min(int(logistics_data.get("delays", 0)) * 5, 50)
        score += min(int(supplier_data.get("supplier_failures", 0)) * 10, 50)
        level = "CRITICAL" if score >= 80 else ("HIGH" if score >= 60 else ("MEDIUM" if score >= 30 else "LOW"))
        r = {"supply_chain_risk_id": f"SCR-{uuid.uuid4()}", "score": score, "risk_level": level,
             "generated_at": datetime.now(timezone.utc).isoformat(), "status": "EVALUATED"}
        self._history.append(r)
        return r
