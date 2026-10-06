
from __future__ import annotations

class RegisterFeedbackUseCase:
    """Registra feedback con validacion 1-10."""

    def __init__(self, satisfaction_engine):
        self._eng = satisfaction_engine

    def execute(self, *, ticket_id, client_id,
                score, comments="") -> dict:
        return self._eng.register(
            ticket_id=ticket_id,
            client_id=client_id, score=score,
            comments=comments)
