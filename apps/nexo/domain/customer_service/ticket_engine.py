
"""Nexo Ticket Engine - adaptador fino (regla 69).
Persistencia en el SupportEngine transversal.
Todas las llamadas keyword-only."""
from __future__ import annotations
from typing import List, Optional

class NexoTicketEngine:
    """Tickets de NEXO via motor transversal."""

    def __init__(self, support_engine,
                 app_id="nexo"):
        self._support = support_engine
        self._app = app_id

    @property
    def mode(self) -> str:
        return "transversal_support"

    def open_ticket(self, *, title,
                    description="",
                    client_id="",
                    priority="NORMAL") -> dict:
        if not str(title).strip():
            raise ValueError(
                "titulo requerido")
        return self._support.create_ticket(
            app_id=self._app, title=title,
            description=description,
            client_id=client_id,
            priority=priority)

    def get(self, ticket_id) -> Optional[dict]:
        return self._support.get_ticket(
            ticket_id)

    def assign(self, *, ticket_id,
               agent_id) -> dict:
        return self._support.assign_ticket(
            ticket_id=ticket_id,
            agent_id=agent_id)

    def resolve(self, *, ticket_id,
                resolution) -> dict:
        return self._support.resolve_ticket(
            ticket_id=ticket_id,
            resolution=resolution)

    def close(self, ticket_id) -> dict:
        return self._support.close_ticket(
            ticket_id=ticket_id)

    def open_tickets(self) -> List[dict]:
        return self._support.get_open_tickets(
            self._app)

    def all_tickets(self) -> List[dict]:
        return self._support.get_tickets_by_app(
            self._app)
