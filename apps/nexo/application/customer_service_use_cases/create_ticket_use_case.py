
from __future__ import annotations

class CreateTicketUseCase:
    """Crea ticket con validacion de titulo."""

    def __init__(self, ticket_engine):
        self._eng = ticket_engine

    def execute(self, *, title, description="",
                client_id="",
                priority="NORMAL") -> dict:
        return self._eng.open_ticket(
            title=title, description=description,
            client_id=client_id,
            priority=priority)
