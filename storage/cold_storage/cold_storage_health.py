from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone


@dataclass(frozen=True, slots=True)
class ColdStorageHealth:
    healthy: bool
    root_available: bool
    checked_at: datetime


class ColdStorageHealthMonitor:
    def check(
        self,
        root_available: bool,
    ) -> ColdStorageHealth:

        return ColdStorageHealth(
            healthy=root_available,
            root_available=root_available,
            checked_at=datetime.now(
                timezone.utc
            ),
        )


__all__ = [
    "ColdStorageHealth",
    "ColdStorageHealthMonitor",
]
