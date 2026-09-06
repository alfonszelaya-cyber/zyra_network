from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone


@dataclass(frozen=True, slots=True)
class MessageHealth:
    healthy: bool
    queue_depth: int
    checked_at: datetime

    def __post_init__(self) -> None:
        if self.queue_depth < 0:
            raise ValueError(
                "queue_depth cannot be negative"
            )


class MessageHealthMonitor:
    def __init__(
        self,
        *,
        max_queue_depth: int = 10000,
    ) -> None:

        if max_queue_depth <= 0:
            raise ValueError(
                "max_queue_depth must be positive"
            )

        self.max_queue_depth = max_queue_depth

    def check(
        self,
        queue_depth: int,
    ) -> MessageHealth:

        return MessageHealth(
            healthy=(
                queue_depth
                <= self.max_queue_depth
            ),
            queue_depth=queue_depth,
            checked_at=datetime.now(
                timezone.utc
            ),
        )


__all__ = [
    "MessageHealth",
    "MessageHealthMonitor",
]
