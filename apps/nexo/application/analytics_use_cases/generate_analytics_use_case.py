
from __future__ import annotations

class GenerateAnalyticsUseCase:
    """Computa y persiste analitica del periodo."""

    def __init__(self, analytics_engine):
        self._eng = analytics_engine

    def execute(self, *, company_id, period,
                records) -> dict:
        return self._eng.compute_from(
            company_id=company_id,
            period=period, records=records)
