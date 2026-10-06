
"""Nexo Service History Engine - historial (NG7)."""
from __future__ import annotations
from typing import Dict, List

class NexoServiceHistoryEngine:
    """Historial y distribucion de tickets."""

    def __init__(self, support_engine,
                 app_id="nexo"):
        self._support = support_engine
        self._app = app_id

    def status_distribution(self) -> Dict[str, int]:
        tickets = self._support.get_tickets_by_app(
            self._app)
        dist = {}
        for t in tickets:
            st = t["status"]
            dist[st] = dist.get(st, 0) + 1
        return dist

    def recent(self, limit=20) -> List[dict]:
        return self._support.get_tickets_by_app(
            self._app)[:limit]

    def ticket_history(self,
                       ticket_id) -> dict:
        t = self._support.get_ticket(ticket_id)
        if not t:
            return {"found": False}
        return {"found": True,
                "ticket": t,
                "age_status": t["status"]}
