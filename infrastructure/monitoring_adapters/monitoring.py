"""Provider-neutral in-process monitoring boundary."""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from threading import RLock
from time import time
from typing import Mapping


class HealthStatus(str, Enum):
    HEALTHY = "healthy"
    DEGRADED = "degraded"
    UNHEALTHY = "unhealthy"


@dataclass(frozen=True, slots=True)
class Metric:
    name: str
    value: float
    timestamp: float
    labels: Mapping[str, str] = field(
        default_factory=dict
    )


class MonitoringAdapter:
    """Thread-safe metric and health state adapter."""

    def __init__(
        self,
        service_name: str,
    ) -> None:
        if not service_name.strip():
            raise ValueError(
                "service_name is required"
            )

        self.service_name = service_name
        self._health = (
            HealthStatus.HEALTHY
        )
        self._metrics: list[
            Metric
        ] = []

        self._lock = RLock()

    def set_health(
        self,
        status: HealthStatus,
    ) -> None:
        if not isinstance(
            status,
            HealthStatus,
        ):
            raise TypeError(
                "status must be HealthStatus"
            )

        with self._lock:
            self._health = status

    def health(
        self,
    ) -> HealthStatus:
        with self._lock:
            return self._health

    def record(
        self,
        name: str,
        value: float,
        labels: Mapping[str, str] | None = None,
    ) -> Metric:
        if not name.strip():
            raise ValueError(
                "metric name is required"
            )

        metric = Metric(
            name=name,
            value=float(value),
            timestamp=time(),
            labels=dict(
                labels or {}
            ),
        )

        with self._lock:
            self._metrics.append(
                metric
            )

        return metric

    def snapshot(
        self,
    ) -> tuple[Metric, ...]:
        with self._lock:
            return tuple(
                self._metrics
            )


__all__ = [
    "HealthStatus",
    "Metric",
    "MonitoringAdapter",
]
