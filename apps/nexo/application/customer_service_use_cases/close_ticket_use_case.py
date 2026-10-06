
from __future__ import annotations

class CloseTicketUseCase:
    """Resuelve con nota y cierra el ticket."""

    def __init__(self, ticket_engine):
        self._eng = ticket_engine

    def execute(self, *, ticket_id,
                resolution) -> dict:
        if not str(resolution).strip():
            raise ValueError(
                "resolution requerida")
        self._eng.resolve(ticket_id=ticket_id,
            resolution=resolution)
        return self._eng.close(ticket_id)
