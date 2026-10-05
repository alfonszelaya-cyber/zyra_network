
"""Executive KPI - NEXO / ZYRA."""
from __future__ import annotations
from datetime import datetime
from typing import Dict, List

class ExecutiveKPIEngine:
    def __init__(self):
        self._history = []

    def _now(self):
        return datetime.utcnow().isoformat()

    def generate_kpis(self, *, metrics):
        kpis = {"revenue_growth": metrics.get("revenue_growth", 0),
                "profit_margin": metrics.get("profit_margin", 0),
                "cash_flow": metrics.get("cash_flow", 0),
                "customer_growth": metrics.get("customer_growth", 0),
                "generated_at": self._now()}
        self._history.append(kpis)
        return kpis

    def get_history(self):
        return list(self._history)

    def get_last_kpis(self):
        return self._history[-1] if self._history else None

    def calculate_executive_score(self, *, kpis):
        values = [float(kpis.get("revenue_growth", 0)),
                  float(kpis.get("profit_margin", 0)),
                  float(kpis.get("cash_flow", 0)),
                  float(kpis.get("customer_growth", 0))]
        if not values:
            return 0.0
        return round(sum(values) / len(values), 2)

    def generate_summary(self):
        last = self.get_last_kpis()
        if not last:
            return {"status": "NO_DATA", "generated_at": self._now()}
        return {"executive_score": self.calculate_executive_score(kpis=last),
                "generated_at": self._now(), "status": "ACTIVE"}

    def generate_report(self):
        return {"report_type": "EXECUTIVE_KPI",
                "records": len(self._history),
                "history": self.get_history(),
                "summary": self.generate_summary(),
                "generated_at": self._now()}
