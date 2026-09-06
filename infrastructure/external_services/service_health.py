from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone


@dataclass(frozen=True, slots=True)
class ServiceHealth:
    service_id: str
    healthy: bool
    latency_ms: float | None
    checked_at: datetime

    def __post_init__(self) -> None:
        if not self.service_id.strip():
            raise ValueError(
                "service_id cannot be empty"
            )

        if (
            self.latency_ms is not None
            and self.latency_ms < 0
        ):
            raise ValueError(
                "latency_ms cannot be negative"
            )


class ServiceHealthMonitor:
    def evaluate(
        self,
        service_id: str,
        *,
        success: bool,
        latency_ms: float | None = None,
    ) -> ServiceHealth:

        return ServiceHealth(
            service_id=service_id.strip(),
            healthy=success,
            latency_ms=latency_ms,
            checked_at=datetime.now(
                timezone.utc
            ),
        )


__all__ = [
    "ServiceHealth",
    "ServiceHealthMonitor",
]
