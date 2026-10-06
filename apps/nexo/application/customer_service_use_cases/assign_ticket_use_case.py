
from __future__ import annotations

class AssignTicketUseCase:
    """Asigna agente a un ticket."""

    def __init__(self, ticket_engine):
        self._eng = ticket_engine

    def execute(self, *, ticket_id,
                agent_id) -> dict:
        t = self._eng.get(ticket_id)
        if not t:
            raise KeyError(ticket_id)
        return self._eng.assign(
            ticket_id=ticket_id,
            agent_id=agent_id)
