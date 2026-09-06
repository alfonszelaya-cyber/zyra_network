from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from uuid import UUID, uuid4


@dataclass(frozen=True, slots=True)
class ShardEvent:
    event_type: str
    shard_id: int
    key: str | None = None
    event_id: UUID = field(
        default_factory=uuid4
    )
    occurred_at: datetime = field(
        default_factory=lambda:
        datetime.now(timezone.utc)
    )

    def __post_init__(self) -> None:
        if not self.event_type.strip():
            raise ValueError(
                "Shard event type cannot be empty"
            )

        if self.shard_id < 0:
            raise ValueError(
                "shard_id cannot be negative"
            )


__all__ = ["ShardEvent"]
