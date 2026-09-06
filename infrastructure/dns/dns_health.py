from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone


@dataclass(frozen=True, slots=True)
class DNSHealth:
    healthy: bool
    resolver_available: bool
    registry_records: int
    checked_at: datetime


class DNSHealthMonitor:
    def check(
        self,
        *,
        resolver_available: bool,
        registry_records: int,
    ) -> DNSHealth:

        if registry_records < 0:
            raise ValueError(
                "registry_records cannot be negative"
            )

        return DNSHealth(
            healthy=resolver_available,
            resolver_available=resolver_available,
            registry_records=registry_records,
            checked_at=datetime.now(
                timezone.utc
            ),
        )


__all__ = [
    "DNSHealth",
    "DNSHealthMonitor",
]
