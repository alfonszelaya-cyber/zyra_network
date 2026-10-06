
from __future__ import annotations

class AnalyzeGovernanceUseCase:
    """Ejecuta analitica de gobernanza."""

    def __init__(self, analytics):
        self._an = analytics

    def execute(self, *, period="") -> dict:
        return self._an.analyze(period=period)
