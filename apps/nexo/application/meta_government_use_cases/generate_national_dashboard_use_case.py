
from __future__ import annotations

class GenerateNationalDashboardUseCase:
    """Genera snapshot del panel nacional."""

    def __init__(self, dashboard):
        self._dash = dashboard

    def execute(self, *, period="") -> dict:
        return self._dash.snapshot(period=period)
