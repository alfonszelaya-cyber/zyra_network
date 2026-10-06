
from __future__ import annotations

class GenerateServiceReportUseCase:
    """Reporte de servicio completo."""

    def __init__(self, cs_facade):
        self._cs = cs_facade

    def execute(self) -> dict:
        return self._cs.service_report()
