
"""Country Risk - NEXO / ZYRA."""
from __future__ import annotations
from datetime import datetime
from typing import Dict, List
import uuid

class CountryRiskEngine:
    def __init__(self):
        self._history = []

    def evaluate(self, *, country_code, geopolitical_data, sanctions_data):
        score = min(int(geopolitical_data.get("risk_score", 0)) + int(sanctions_data.get("risk_score", 0)), 100)
        level = "CRITICAL" if score >= 80 else ("HIGH" if score >= 60 else ("MEDIUM" if score >= 30 else "LOW"))
        r = {"risk_id": f"CTR-{uuid.uuid4()}", "country": country_code,
             "score": score, "level": level,
             "generated_at": datetime.utcnow().isoformat(), "status": "ACTIVE"}
        self._history.append(r)
        return r
