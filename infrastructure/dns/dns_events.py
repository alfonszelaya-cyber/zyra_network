from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from uuid import UUID, uuid4


@dataclass(frozen=True, slots=True)
class DNSEvent:
    event_type: str
    hostname: str
    addresses: tuple[str, ...] = ()
    event_id: UUID = uuid4()
    occurred_at: datetime = datetime.now(
        timezone.utc
    )

    def __post_init__(self) -> None:
        if not self.event_type.strip():
            raise ValueError(
                "DNS event type cannot be empty"
            )

        if not self.hostname.strip():
            raise ValueError(
                "DNS hostname cannot be empty"
            )

        object.__setattr__(
            self,
            "event_id",
            self.event_id,
        )

        object.__setattr__(
            self,
            "occurred_at",
            self.occurred_at,
        )


__all__ = ["DNSEvent"]
