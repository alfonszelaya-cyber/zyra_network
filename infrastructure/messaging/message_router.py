from __future__ import annotations

from dataclasses import dataclass
from threading import RLock
from typing import Callable


RouteHandler = Callable[[object], object]


@dataclass(frozen=True, slots=True)
class MessageRoute:
    topic: str
    handler: RouteHandler


class MessageRouter:
    def __init__(self) -> None:
        self._routes: dict[
            str,
            list[RouteHandler],
        ] = {}
        self._lock = RLock()

    def add_route(
        self,
        topic: str,
        handler: RouteHandler,
    ) -> None:

        topic = topic.strip()

        if not topic:
            raise ValueError(
                "Message route topic cannot be empty"
            )

        if not callable(handler):
            raise TypeError(
                "Message route handler must be callable"
            )

        with self._lock:
            self._routes.setdefault(
                topic,
                [],
            ).append(handler)

    def remove_route(
        self,
        topic: str,
        handler: RouteHandler,
    ) -> bool:

        topic = topic.strip()

        with self._lock:
            handlers = self._routes.get(topic)

            if not handlers or handler not in handlers:
                return False

            handlers.remove(handler)

            if not handlers:
                self._routes.pop(topic)

            return True

    def dispatch(
        self,
        topic: str,
        message: object,
    ) -> list[object]:

        with self._lock:
            handlers = tuple(
                self._routes.get(
                    topic.strip(),
                    (),
                )
            )

        return [
            handler(message)
            for handler in handlers
        ]

    def topics(self) -> tuple[str, ...]:
        with self._lock:
            return tuple(
                sorted(self._routes)
            )


__all__ = [
    "MessageRoute",
    "MessageRouter",
]
