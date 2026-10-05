
"""Executive Decision - NEXO / ZYRA."""
from __future__ import annotations
from datetime import datetime
from uuid import uuid4
from typing import Dict, List, Optional

class ExecutiveDecisionEngine:
    VALID_STATUS = ("READY", "APPROVED", "REJECTED", "EXECUTED", "CANCELLED")

    def __init__(self):
        self._decisions = []

    def _now(self):
        return datetime.utcnow().isoformat()

    def support_decision(self, *, decision_context,
                         recommendation="REVIEW_REQUIRED", priority="NORMAL"):
        d = {"decision_id": f"DEC-{uuid4()}", "generated_at": self._now(),
             "context": decision_context, "recommendation": recommendation,
             "priority": priority, "status": "READY"}
        self._decisions.append(d)
        return d

    def get_decision(self, decision_id):
        for d in self._decisions:
            if d["decision_id"] == decision_id:
                return d
        return None

    def get_decisions(self):
        return list(self._decisions)

    def update_status(self, decision_id, status):
        if status not in self.VALID_STATUS:
            return None
        d = self.get_decision(decision_id)
        if not d:
            return None
        d["status"] = status
        d["updated_at"] = self._now()
        return d

    def evaluate_impact(self, *, decision_id, financial, operational, compliance):
        d = self.get_decision(decision_id)
        if not d:
            return None
        d["impact"] = {"financial": financial, "operational": operational,
                       "compliance": compliance}
        d["updated_at"] = self._now()
        return d

    def generate_summary(self):
        return {"total_decisions": len(self._decisions),
                "ready": len([d for d in self._decisions if d["status"] == "READY"]),
                "approved": len([d for d in self._decisions if d["status"] == "APPROVED"]),
                "executed": len([d for d in self._decisions if d["status"] == "EXECUTED"]),
                "generated_at": self._now()}

    def generate_report(self):
        return {"report_type": "EXECUTIVE_DECISIONS",
                "decisions": self.get_decisions(),
                "summary": self.generate_summary(),
                "generated_at": self._now()}
