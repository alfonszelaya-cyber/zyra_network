
from __future__ import annotations

class AnalyzeBusinessMetricsUseCase:
    """KPIs de negocio entre periodos."""

    def __init__(self, business_metrics):
        self._eng = business_metrics

    def execute(self, *, current_income,
                current_expense,
                previous_income="0") -> dict:
        return self._eng.snapshot(
            income=current_income,
            expense=current_expense,
            previous_income=previous_income)
