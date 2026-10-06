
from __future__ import annotations

class CalculateSatisfactionUseCase:
    """Satisfaccion promedio NEXO."""

    def __init__(self, satisfaction_engine):
        self._eng = satisfaction_engine

    def execute(self) -> dict:
        return self._eng.average()
