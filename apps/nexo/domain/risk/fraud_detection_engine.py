
"""Fraud Detection - NEXO / ZYRA."""
from __future__ import annotations
from datetime import datetime
from typing import Dict, List
import uuid

class FraudDetectionEngine:
    def __init__(self):
        self._history = []

    def detect(self, *, client_data, accounting_data, operations_data):
        score = 0
        flags = []
        if int(accounting_data.get("duplicate_transactions", 0)) > 0:
            score += 30; flags.append("DUPLICATE_TRANSACTIONS")
        if accounting_data.get("unusual_amounts", False):
            score += 30; flags.append("UNUSUAL_AMOUNTS")
        if operations_data.get("abnormal_activity", False):
            score += 40; flags.append("ABNORMAL_ACTIVITY")
        level = "CRITICAL" if score >= 80 else ("HIGH" if score >= 50 else ("MEDIUM" if score >= 25 else "LOW"))
        r = {"fraud_id": f"FRD-{uuid.uuid4()}", "client_id": client_data.get("client_id"),
             "score": score, "level": level, "flags": flags,
             "generated_at": datetime.utcnow().isoformat(), "status": "ANALYZED"}
        self._history.append(r)
        return r
