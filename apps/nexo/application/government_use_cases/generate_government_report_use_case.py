
from __future__ import annotations

class GenerateGovernmentReportUseCase:
    """Genera reporte de rendicion de cuentas."""

    def __init__(self, reporting):
        self._rep = reporting

    def execute(self, *, institution_id,
                period) -> dict:
        return self._rep.accountability_report(
            institution_id, period)
