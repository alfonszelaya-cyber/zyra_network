
"""Operational Risk - NEXO / ZYRA."""
from __future__ import annotations
from datetime import datetime
from typing import Dict, List
import uuid

class OperationalRiskEngine:
    def __init__(self):
        self._history = []

    def evaluate(self, *, logistics_data, operations_data):
        score = 0
        score += min(int(logistics_data.get("delayed_shipments", 0)) * 2, 30)
        score += min(int(operations_data.get("failed_processes", 0)) * 5, 40)
        score += min(int(operations_data.get("incidents", 0)) * 10, 30)
        level = "CRITICAL" if score >= 80 else ("HIGH" if score >= 60 else ("MEDIUM" if score >= 30 else "LOW"))
        r = {"risk_id": f"OPR-{uuid.uuid4()}", "score": score, "level": level,
             "generated_at": datetime.utcnow().isoformat(), "status": "EVALUATED"}
        self._history.append(r)
        return r
