
"""Executive Report - NEXO / ZYRA."""
from __future__ import annotations
from datetime import datetime, timezone
from uuid import uuid4
from typing import Dict, List, Optional

class ExecutiveReportEngine:
    def __init__(self):
        self._reports = []

    def _now(self):
        return datetime.now(timezone.utc).isoformat()

    def generate_report(self, *, dashboard_data, report_scope="GLOBAL"):
        report = {"report_id": f"EXR-{uuid4()}",
                  "generated_at": self._now(),
                  "report_type": "EXECUTIVE",
                  "report_scope": report_scope,
                  "data": dashboard_data, "status": "GENERATED"}
        self._reports.append(report)
        return report

    def get_reports(self):
        return list(self._reports)

    def get_report(self, report_id):
        for r in self._reports:
            if r["report_id"] == report_id:
                return r
        return None

    def get_last_report(self):
        return self._reports[-1] if self._reports else None

    def generate_summary(self):
        return {"total_reports": len(self._reports),
                "generated_at": self._now(), "status": "ACTIVE"}

    def export_report(self, report_id):
        report = self.get_report(report_id)
        if not report:
            return None
        return {"report_id": report["report_id"],
                "exported_at": self._now(),
                "status": "EXPORTED", "data": report}

    def generate_global_report(self):
        return {"report_type": "EXECUTIVE_REPORT_ENGINE",
                "reports": self.get_reports(),
                "summary": self.generate_summary(),
                "generated_at": self._now()}
