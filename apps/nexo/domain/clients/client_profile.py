
# client_profile.py - NEXO / ZYRA (migrado)
from __future__ import annotations
from typing import Dict, List
from datetime import datetime, timezone

class ClientProfile:
    """Perfil ejecutivo consolidado del cliente."""

    def _now(self):
        return datetime.now(timezone.utc).isoformat()

    def calculate_risk_level(self, history: List[dict]) -> str:
        risk_events = len([
            x for x in history
            if x.get("event_type") in (
                "RISK", "COMPLIANCE", "AUDIT")])
        if risk_events >= 20:
            return "CRITICAL"
        if risk_events >= 10:
            return "HIGH"
        if risk_events >= 5:
            return "MEDIUM"
        return "NORMAL"

    def calculate_zyra_score(self, history: List[dict]) -> int:
        score = 100
        for item in history:
            et = item.get("event_type", "")
            if et == "RISK":
                score -= 10
            elif et == "COMPLIANCE":
                score -= 15
            elif et == "AUDIT":
                score -= 5
        return max(score, 0)

    def build_profile(self, client_data: Dict,
                      history: List[dict],
                      companies: List[dict]) -> Dict:
        return {"client": client_data,
                "history": history,
                "companies": companies,
                "risk_level": self.calculate_risk_level(history),
                "zyra_score": self.calculate_zyra_score(history),
                "profile_completed": True,
                "total_events": len(history),
                "total_companies": len(companies),
                "financial_score": client_data.get("financial_score", 0),
                "fiscal_score": client_data.get("fiscal_score", 0),
                "operational_score": client_data.get("operational_score", 0),
                "status": client_data.get("status", "ACTIVE"),
                "generated_at": self._now()}

    def executive_summary(self, profile: Dict) -> Dict:
        return {"client_id": profile["client"].get("client_id"),
                "name": profile["client"].get("name"),
                "status": profile.get("status"),
                "risk_level": profile.get("risk_level"),
                "zyra_score": profile.get("zyra_score"),
                "companies": profile.get("total_companies"),
                "events": profile.get("total_events"),
                "generated_at": self._now()}
