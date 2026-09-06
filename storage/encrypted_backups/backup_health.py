from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone


@dataclass(frozen=True, slots=True)
class BackupHealth:
    healthy: bool
    storage_available: bool
    checked_at: datetime


class BackupHealthMonitor:
    def check(
        self,
        storage_available: bool,
    ) -> BackupHealth:

        return BackupHealth(
            healthy=storage_available,
            storage_available=storage_available,
            checked_at=datetime.now(
                timezone.utc
            ),
        )


__all__ = [
    "BackupHealth",
    "BackupHealthMonitor",
]
