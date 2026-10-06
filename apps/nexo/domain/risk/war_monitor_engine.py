
"""War Monitor - NEXO / ZYRA."""
from __future__ import annotations
from datetime import datetime, timezone
from typing import Dict, List
import uuid

class WarMonitorEngine:
    def __init__(self):
        self._history = []

    def evaluate(self, *, country_data):
        score = int(country_data.get("military_risk", 0))
        if country_data.get("active_conflict", False): score = max(score, 90)
        level = "CRITICAL" if score >= 85 else ("HIGH" if score >= 70 else ("MEDIUM" if score >= 40 else "LOW"))
        r = {"war_risk_id": f"WAR-{uuid.uuid4()}", "country": country_data.get("country"),
             "active_conflict": country_data.get("active_conflict", False),
             "score": score, "risk_level": level,
             "generated_at": datetime.now(timezone.utc).isoformat(), "status": "MONITORED"}
        self._history.append(r)
        return r
