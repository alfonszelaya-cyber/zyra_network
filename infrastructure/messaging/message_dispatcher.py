from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Mapping

from .message_events import MessageEvent
from .message_router import MessageRouter
from .message_validator import MessageValidator


@dataclass(frozen=True, slots=True)
class DispatchResult:
    topic: str
    handler_results: tuple[Any, ...]


class MessageDispatcher:
    def __init__(
        self,
        router: MessageRouter,
        validator: MessageValidator | None = None,
    ) -> None:

        self.router = router
        self.validator = (
            validator
            or MessageValidator()
        )

    def dispatch(
        self,
        topic: str,
        payload: Mapping[str, Any],
    ) -> DispatchResult:

        self.validator.require_valid(
            topic,
            payload,
        )

        event = MessageEvent(
            topic=topic,
            payload=payload,
        )

        results = self.router.dispatch(
            event.topic,
            event,
        )

        return DispatchResult(
            topic=event.topic,
            handler_results=tuple(results),
        )


__all__ = [
    "DispatchResult",
    "MessageDispatcher",
]
