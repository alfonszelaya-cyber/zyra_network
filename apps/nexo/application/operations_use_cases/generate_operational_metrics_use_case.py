
from __future__ import annotations
from apps.nexo.domain.operations.operational_metrics_engine import (
    OperationalMetricsEngine)

class GenerateOperationalMetricsUseCase:
    """Calcula y persiste metricas del periodo
    (repara calculate_metrics(period=...) del viejo)."""

    def __init__(self, metrics):
        self._metrics = metrics

    def execute(self, *, company_id, period) -> dict:
        r = self._metrics.compute_company_metrics(
            company_id=company_id, period=period)
        r["stored"] = self._metrics.get_metrics(
            company_id, period)
        return r
