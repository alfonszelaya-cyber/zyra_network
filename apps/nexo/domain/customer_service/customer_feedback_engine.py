
"""Nexo Feedback Engine - feedback con resumen."""
from __future__ import annotations

class NexoFeedbackEngine:
    """Feedback NEXO + resumen agregado."""

    def __init__(self, support_engine,
                 app_id="nexo"):
        self._support = support_engine
        self._app = app_id

    def register(self, *, ticket_id, client_id,
                 score, comments="") -> dict:
        return self._support.register_feedback(
            ticket_id=ticket_id,
            client_id=client_id, score=score,
            comments=comments)

    def summary(self) -> dict:
        avg = (self._support.
               average_satisfaction(
                   self._app))
        tickets = (self._support.
                   get_tickets_by_app(
                       self._app))
        return {"tickets": len(tickets),
                "satisfaction": avg}
