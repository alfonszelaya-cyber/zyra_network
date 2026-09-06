from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from uuid import UUID, uuid4


@dataclass(frozen=True, slots=True)
class BackupEvent:
    event_type: str
    backup_id: UUID
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
                "Backup event type cannot be empty"
            )


__all__ = ["BackupEvent"]
