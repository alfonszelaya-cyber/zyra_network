from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any, Mapping
from uuid import UUID, uuid4


@dataclass(frozen=True, slots=True)
class ProtocolEvent:
    name: str
    source: str
    payload: Mapping[str, Any] = field(default_factory=dict)
    event_id: UUID = field(default_factory=uuid4)
    created_at: datetime = field(
        default_factory=lambda: datetime.now(timezone.utc)
    )

    def __post_init__(self) -> None:
        if not self.name.strip():
            raise ValueError("Event name cannot be empty")
        if not self.source.strip():
            raise ValueError("Event source cannot be empty")

        object.__setattr__(self, "payload", dict(self.payload))


class EventBus:
    def __init__(self) -> None:
        self._handlers: dict[str, list] = {}

    def subscribe(self, event_name: str, handler) -> None:
        if not callable(handler):
            raise TypeError("Event handler must be callable")

        name = event_name.strip()

        if not name:
            raise ValueError("Event name cannot be empty")

        handlers = self._handlers.setdefault(name, [])

        if handler not in handlers:
            handlers.append(handler)

    def unsubscribe(self, event_name: str, handler) -> bool:
        handlers = self._handlers.get(event_name.strip())

        if not handlers or handler not in handlers:
            return False

        handlers.remove(handler)

        if not handlers:
            self._handlers.pop(event_name.strip(), None)

        return True

    def publish(self, event: ProtocolEvent) -> list[Any]:
        handlers = tuple(
            self._handlers.get(event.name, ())
        )

        return [
            handler(event)
            for handler in handlers
        ]


__all__ = ["ProtocolEvent", "EventBus"]
