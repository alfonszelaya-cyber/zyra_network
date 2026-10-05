
from __future__ import annotations
from apps.nexo.domain.executive.executive_metrics_engine import ExecutiveMetricsEngine

class AnalyzeMetricsUseCase:
    def __init__(self, metrics_engine):
        self._engine = metrics_engine

    def execute(self, *, source_data):
        return self._engine.calculate_metrics(source_data=source_data)
