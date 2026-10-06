
"""Risk Monitor - NEXO / ZYRA."""
from __future__ import annotations
from datetime import datetime, timezone
from typing import Dict, List
import uuid

class RiskMonitorEngine:
    def __init__(self):
        self._events = []

    def register(self, risk_result):
        e = {"event_id": f"RM-{uuid.uuid4()}", "risk_id": risk_result.get("risk_id"),
             "risk_level": risk_result.get("level"), "score": risk_result.get("score"),
             "created_at": datetime.now(timezone.utc).isoformat(), "status": "MONITORED"}
        self._events.append(e)
        return e

    def get_active_alerts(self):
        return [e for e in self._events if e.get("risk_level") in ("HIGH", "CRITICAL")]
