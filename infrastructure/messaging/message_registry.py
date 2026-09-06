from __future__ import annotations

from dataclasses import dataclass
from threading import RLock
from typing import Any, Callable


MessageHandler = Callable[[Any], Any]


@dataclass(frozen=True, slots=True)
class MessageHandlerRecord:
    name: str
    handler: MessageHandler
    enabled: bool = True


class MessageRegistry:
    def __init__(self) -> None:
        self._handlers: dict[
            str,
            MessageHandlerRecord,
        ] = {}
        self._lock = RLock()

    def register(
        self,
        name: str,
        handler: MessageHandler,
        *,
        replace: bool = False,
    ) -> None:

        name = name.strip()

        if not name:
            raise ValueError(
                "Handler name cannot be empty"
            )

        if not callable(handler):
            raise TypeError(
                "Message handler must be callable"
            )

        with self._lock:
            if name in self._handlers and not replace:
                raise ValueError(
                    f"Message handler already registered: {name}"
                )

            self._handlers[name] = MessageHandlerRecord(
                name=name,
                handler=handler,
            )

    def unregister(self, name: str) -> bool:
        with self._lock:
            return (
                self._handlers.pop(
                    name.strip(),
                    None,
                )
                is not None
            )

    def resolve(
        self,
        name: str,
    ) -> MessageHandlerRecord:

        with self._lock:
            try:
                return self._handlers[name.strip()]
            except KeyError as exc:
                raise LookupError(
                    f"Message handler not found: {name}"
                ) from exc

    def names(self) -> tuple[str, ...]:
        with self._lock:
            return tuple(sorted(self._handlers))


__all__ = [
    "MessageHandler",
    "MessageHandlerRecord",
    "MessageRegistry",
]
