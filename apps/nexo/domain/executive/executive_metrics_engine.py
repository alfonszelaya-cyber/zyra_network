
"""Executive Metrics - NEXO / ZYRA."""
from __future__ import annotations
from datetime import datetime
from typing import Dict, List, Optional

class ExecutiveMetricsEngine:
    def __init__(self):
        self._metrics_history = []

    def _now(self):
        return datetime.utcnow().isoformat()

    def calculate_metrics(self, *, source_data):
        m = {"generated_at": self._now(), "metrics": source_data,
             "status": "CALCULATED"}
        self._metrics_history.append(m)
        return m

    def get_metrics_history(self):
        return list(self._metrics_history)

    def get_last_metrics(self):
        return self._metrics_history[-1] if self._metrics_history else None

    def generate_summary(self):
        if not self._metrics_history:
            return {"status": "NO_DATA", "generated_at": self._now()}
        return {"records": len(self._metrics_history),
                "generated_at": self._now(), "status": "ACTIVE"}

    def generate_report(self):
        return {"report_type": "EXECUTIVE_METRICS",
                "history": self.get_metrics_history(),
                "summary": self.generate_summary(),
                "generated_at": self._now()}
