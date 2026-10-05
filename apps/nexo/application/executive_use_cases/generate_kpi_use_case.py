
from __future__ import annotations
from apps.nexo.domain.executive.executive_kpi_engine import ExecutiveKPIEngine

class GenerateKPIUseCase:
    def __init__(self, kpi_engine):
        self._engine = kpi_engine

    def execute(self, *, metrics):
        return self._engine.generate_kpis(metrics=metrics)
