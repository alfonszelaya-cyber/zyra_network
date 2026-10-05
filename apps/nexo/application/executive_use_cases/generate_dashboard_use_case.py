
from __future__ import annotations
from apps.nexo.domain.executive.executive_dashboard_engine import ExecutiveDashboardEngine

class GenerateDashboardUseCase:
    def __init__(self, dashboard_engine):
        self._engine = dashboard_engine

    def execute(self, *, kpis, metrics, alerts, decisions):
        return self._engine.build_dashboard(
            kpis=kpis, metrics=metrics, alerts=alerts,
            decisions=decisions)
