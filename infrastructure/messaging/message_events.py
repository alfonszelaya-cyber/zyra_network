from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any, Mapping
from uuid import UUID, uuid4


@dataclass(frozen=True, slots=True)
class MessageEvent:
    topic: str
    payload: Mapping[str, Any]
    event_id: UUID = field(default_factory=uuid4)
    occurred_at: datetime = field(
        default_factory=lambda: datetime.now(timezone.utc)
    )
    correlation_id: UUID | None = None

    def __post_init__(self) -> None:
        topic = self.topic.strip()

        if not topic:
            raise ValueError(
                "Message event topic cannot be empty"
            )

        if self.occurred_at.tzinfo is None:
            raise ValueError(
                "Message event timestamp must be timezone-aware"
            )

        object.__setattr__(self, "topic", topic)
        object.__setattr__(
            self,
            "payload",
            dict(self.payload),
        )

    def to_dict(self) -> dict[str, Any]:
        return {
            "event_id": str(self.event_id),
            "topic": self.topic,
            "payload": dict(self.payload),
            "occurred_at": self.occurred_at.astimezone(
                timezone.utc
            ).isoformat(),
            "correlation_id": (
                str(self.correlation_id)
                if self.correlation_id
                else None
            ),
        }


__all__ = ["MessageEvent"]
