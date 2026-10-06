
from __future__ import annotations

class EscalateTicketUseCase:
    """Escala ticket NEXO a otra app."""

    def __init__(self, escalation_engine):
        self._eng = escalation_engine

    def execute(self, *, ticket_id, to_app,
                level="HIGH",
                reason="") -> dict:
        return self._eng.escalate(
            ticket_id=ticket_id, to_app=to_app,
            level=level, reason=reason)
