
from __future__ import annotations
from apps.nexo.domain.executive.executive_report_engine import ExecutiveReportEngine

class GenerateExecutiveReportUseCase:
    def __init__(self, report_engine):
        self._engine = report_engine

    def execute(self, *, dashboard_data, report_scope="GLOBAL"):
        return self._engine.generate_report(
            dashboard_data=dashboard_data, report_scope=report_scope)
