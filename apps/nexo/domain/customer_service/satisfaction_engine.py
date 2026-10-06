
"""Nexo Satisfaction Engine - satisfaccion y
feedback (delega al transversal)."""
from __future__ import annotations

class NexoSatisfactionEngine:
    """Satisfaccion de clientes NEXO."""

    def __init__(self, support_engine,
                 app_id="nexo"):
        self._support = support_engine
        self._app = app_id

    def register(self, *, ticket_id, client_id,
                 score,
                 comments="") -> dict:
        if score < 1 or score > 10:
            raise ValueError(
                "score entre 1 y 10")
        return self._support.register_feedback(
            ticket_id=ticket_id,
            client_id=client_id, score=score,
            comments=comments)

    def average(self) -> dict:
        return self._support.average_satisfaction(
            self._app)
