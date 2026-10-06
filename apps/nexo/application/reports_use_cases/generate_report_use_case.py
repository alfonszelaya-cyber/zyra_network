
from __future__ import annotations

class GenerateReportUseCase:
    """Genera reporte formal persistido."""

    def __init__(self, report_engine):
        self._eng = report_engine

    def execute(self, *, report_type,
                company_id="", period="",
                data=None) -> dict:
        return self._eng.generate(
            report_type=report_type,
            company_id=company_id,
            period=period, data=data)
