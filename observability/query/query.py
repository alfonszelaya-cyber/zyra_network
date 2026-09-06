from __future__ import annotations

from datetime import datetime

from ..core import (
    MetricRegistry,
    MetricSample,
)


class ObservationQuery:
    def __init__(
        self,
        metric_registry: MetricRegistry,
    ) -> None:

        self.metric_registry = metric_registry

    def metrics(
        self,
        name: str | None = None,
        *,
        start: datetime | None = None,
        end: datetime | None = None,
        labels: dict | None = None,
    ) -> list[MetricSample]:

        return self.metric_registry.query(
            name,
            start=start,
            end=end,
            labels=labels,
        )


__all__ = ["ObservationQuery"]
