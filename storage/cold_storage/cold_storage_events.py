from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from uuid import UUID, uuid4


@dataclass(frozen=True, slots=True)
class ColdStorageEvent:
    event_type: str
    key: str
    object_id: UUID | None = None
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
                "Storage event type cannot be empty"
            )

        if not self.key.strip():
            raise ValueError(
                "Storage event key cannot be empty"
            )


__all__ = ["ColdStorageEvent"]
