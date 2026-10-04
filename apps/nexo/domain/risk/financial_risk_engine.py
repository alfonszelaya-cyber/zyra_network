
"""Financial Risk - NEXO / ZYRA."""
from __future__ import annotations
from datetime import datetime
from typing import Dict, List
import uuid

class FinancialRiskEngine:
    def __init__(self):
        self._history = []

    def evaluate(self, *, accounting_data, finance_data):
        score = 0
        if float(finance_data.get("liquidity_ratio", 0)) < 1: score += 40
        if float(finance_data.get("debt_ratio", 0)) > 70: score += 40
        if accounting_data.get("negative_cashflow", False): score += 20
        level = "CRITICAL" if score >= 80 else ("HIGH" if score >= 60 else ("MEDIUM" if score >= 30 else "LOW"))
        r = {"risk_id": f"FIN-{uuid.uuid4()}", "score": score, "level": level,
             "generated_at": datetime.utcnow().isoformat(), "status": "EVALUATED"}
        self._history.append(r)
        return r
