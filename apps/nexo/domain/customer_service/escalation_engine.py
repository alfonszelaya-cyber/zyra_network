
"""Nexo Escalation Engine - escalamiento cross-app
desde NEXO (Modulo 10 del viejo diseno)."""
from __future__ import annotations
from typing import List

class NexoEscalationEngine:
    """Escalamientos NEXO -> otras apps."""

    def __init__(self, support_engine,
                 app_id="nexo"):
        self._support = support_engine
        self._app = app_id

    def escalate(self, *, ticket_id, to_app,
                 level="HIGH",
                 reason="") -> dict:
        return self._support.escalate_ticket(
            ticket_id=ticket_id, to_app=to_app,
            level=level, reason=reason)

    def open_escalated(self) -> List[dict]:
        return [t for t in
                self._support.get_open_tickets(
                    self._app)
                if t["status"] == "ESCALATED"]
