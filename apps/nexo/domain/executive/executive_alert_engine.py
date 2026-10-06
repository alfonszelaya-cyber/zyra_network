
"""Executive Alert - NEXO / ZYRA."""
from __future__ import annotations
from datetime import datetime, timezone
from uuid import uuid4
from typing import Dict, List, Optional

class ExecutiveAlertEngine:
    VALID_LEVELS = ("INFO", "LOW", "MEDIUM", "HIGH", "CRITICAL")
    VALID_STATUS = ("OPEN", "IN_PROGRESS", "RESOLVED", "CLOSED", "ESCALATED")

    def __init__(self):
        self._alerts = []

    def _now(self):
        return datetime.now(timezone.utc).isoformat()

    def validate_alert(self, level, title, description):
        if level not in self.VALID_LEVELS:
            return False
        if not title:
            return False
        if not description:
            return False
        return True

    def create_alert(self, *, level, title, description,
                     source_module=None, reference_id=None, metadata=None):
        if not self.validate_alert(level, title, description):
            raise ValueError("Invalid alert data")
        alert = {"alert_id": f"ALT-{uuid4()}", "level": level, "title": title,
                 "description": description, "source_module": source_module,
                 "reference_id": reference_id, "metadata": metadata or {},
                 "status": "OPEN", "created_at": self._now(),
                 "updated_at": self._now()}
        self._alerts.append(alert)
        return alert

    def get_alert(self, alert_id):
        for a in self._alerts:
            if a["alert_id"] == alert_id:
                return a
        return None

    def get_alerts(self):
        return list(self._alerts)

    def get_open_alerts(self):
        return [a for a in self._alerts if a["status"] == "OPEN"]

    def get_critical_alerts(self):
        return [a for a in self._alerts if a["level"] == "CRITICAL"]

    def update_status(self, alert_id, status):
        if status not in self.VALID_STATUS:
            return None
        alert = self.get_alert(alert_id)
        if not alert:
            return None
        alert["status"] = status
        alert["updated_at"] = self._now()
        return alert

    def escalate_alert(self, alert_id):
        alert = self.get_alert(alert_id)
        if not alert:
            return None
        alert["status"] = "ESCALATED"
        alert["updated_at"] = self._now()
        return alert

    def close_alert(self, alert_id):
        alert = self.update_status(alert_id, "CLOSED")
        if alert:
            alert["closed_at"] = self._now()
        return alert

    def generate_summary(self):
        return {"total_alerts": len(self._alerts),
                "open_alerts": len(self.get_open_alerts()),
                "critical_alerts": len(self.get_critical_alerts()),
                "generated_at": self._now()}

    def generate_report(self):
        return {"report_type": "EXECUTIVE_ALERTS",
                "alerts": self.get_alerts(),
                "summary": self.generate_summary(),
                "generated_at": self._now()}
