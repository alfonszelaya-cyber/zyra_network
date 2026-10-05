
"""Executive Monitor - NEXO / ZYRA."""
from __future__ import annotations
from datetime import datetime
from typing import Dict, List, Optional

class ExecutiveMonitorEngine:
    def __init__(self):
        self._monitoring_history = []

    def _now(self):
        return datetime.utcnow().isoformat()

    def monitor_business(self, *, indicators):
        m = {"checked_at": self._now(), "indicators": indicators,
             "status": "MONITORED"}
        self._monitoring_history.append(m)
        return m

    def get_monitoring_history(self):
        return list(self._monitoring_history)

    def get_last_monitoring(self):
        return self._monitoring_history[-1] if self._monitoring_history else None

    def detect_anomalies(self, *, indicators, threshold=100.0):
        anomalies = []
        for key, value in indicators.items():
            if isinstance(value, (int, float)):
                if value > threshold:
                    anomalies.append({"indicator": key, "value": value,
                                      "threshold": threshold,
                                      "detected_at": self._now()})
        return anomalies

    def generate_summary(self):
        return {"monitoring_records": len(self._monitoring_history),
                "generated_at": self._now(), "status": "ACTIVE"}

    def generate_report(self):
        return {"report_type": "EXECUTIVE_MONITOR",
                "history": self.get_monitoring_history(),
                "summary": self.generate_summary(),
                "generated_at": self._now()}
