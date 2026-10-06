
"""Global Alert - NEXO / ZYRA."""
from __future__ import annotations
from datetime import datetime, timezone
from typing import Dict, List
import uuid

class GlobalAlertEngine:
    def __init__(self):
        self._alerts = []

    def create_alert(self, *, compliance_risk, country_risk, financial_risk,
                     fraud_risk, geopolitical_risk):
        scores = [compliance_risk.get("score", 0), country_risk.get("score", 0),
                  financial_risk.get("score", 0), fraud_risk.get("score", 0),
                  geopolitical_risk.get("score", 0)]
        gs = max(scores)
        level = "CRITICAL" if gs >= 80 else ("HIGH" if gs >= 60 else ("MEDIUM" if gs >= 30 else "LOW"))
        alert = {"alert_id": f"ALT-{uuid.uuid4()}", "global_score": gs, "level": level,
                 "created_at": datetime.now(timezone.utc).isoformat(), "status": "OPEN"}
        self._alerts.append(alert)
        return alert
