
"""Geopolitical Risk - NEXO / ZYRA."""
from __future__ import annotations
from datetime import datetime, timezone
from typing import Dict, List
import uuid

class GeopoliticalRiskEngine:
    def __init__(self):
        self._history = []

    def evaluate(self, *, country_code, geopolitical_events):
        score = int(geopolitical_events.get("risk_score", 0))
        level = "CRITICAL" if score >= 80 else ("HIGH" if score >= 60 else ("MEDIUM" if score >= 30 else "LOW"))
        r = {"risk_id": f"GEO-{uuid.uuid4()}", "country": country_code,
             "score": score, "level": level,
             "generated_at": datetime.now(timezone.utc).isoformat(), "status": "ACTIVE"}
        self._history.append(r)
        return r
