
"""Executive Dashboard - NEXO / ZYRA."""
from __future__ import annotations
from datetime import datetime, timezone
from typing import Dict, List

class ExecutiveDashboardEngine:
    def __init__(self):
        self._snapshots = []

    def _now(self):
        return datetime.now(timezone.utc).isoformat()

    def build_dashboard(self, *, kpis, metrics, alerts, decisions):
        critical = len([a for a in alerts if a.get("level") == "CRITICAL"])
        open_a = len([a for a in alerts if a.get("status") == "OPEN"])
        d = {"generated_at": self._now(), "kpis": kpis, "metrics": metrics,
             "alerts": alerts, "decisions": decisions,
             "critical_alerts": critical, "open_alerts": open_a,
             "total_decisions": len(decisions), "status": "ACTIVE"}
        self._snapshots.append(d)
        return d

    def get_snapshots(self):
        return list(self._snapshots)

    def get_last_snapshot(self):
        return self._snapshots[-1] if self._snapshots else None

    def generate_executive_summary(self):
        d = self.get_last_snapshot()
        if not d:
            return {"status": "NO_DATA", "generated_at": self._now()}
        return {"generated_at": self._now(), "critical_alerts": d["critical_alerts"],
                "open_alerts": d["open_alerts"],
                "total_decisions": d["total_decisions"], "status": d["status"]}

    def generate_report(self):
        return {"report_type": "EXECUTIVE_DASHBOARD",
                "snapshots": self.get_snapshots(),
                "generated_at": self._now()}
