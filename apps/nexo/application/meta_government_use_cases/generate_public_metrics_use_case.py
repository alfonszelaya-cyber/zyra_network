
from __future__ import annotations

class GeneratePublicMetricsUseCase:
    """Publica metrica y devuelve la mas reciente."""

    def __init__(self, metrics):
        self._met = metrics

    def execute(self, *, name, period, value,
                unit="") -> dict:
        self._met.publish_metric(
            name=name, period=period,
            value=value, unit=unit)
        return self._met.latest(name)
