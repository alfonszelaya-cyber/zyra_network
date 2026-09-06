from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone


@dataclass(frozen=True, slots=True)
class ShardHealth:
    healthy: bool
    registered_shards: int
    checked_at: datetime


class ShardHealthMonitor:
    def check(
        self,
        registered_shards: int,
    ) -> ShardHealth:

        if registered_shards < 0:
            raise ValueError(
                "registered_shards cannot be negative"
            )

        return ShardHealth(
            healthy=(
                registered_shards > 0
            ),
            registered_shards=(
                registered_shards
            ),
            checked_at=datetime.now(
                timezone.utc
            ),
        )


__all__ = [
    "ShardHealth",
    "ShardHealthMonitor",
]
