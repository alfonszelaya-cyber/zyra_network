from __future__ import annotations

from collections import defaultdict
from threading import RLock
from typing import Any, Callable


Hook = Callable[..., Any]


class HookError(RuntimeError):
    """Raised when a hook operation fails."""


class HookRegistry:
    """
    Thread-safe local hook registry.

    Foundation hooks provide synchronous lifecycle extension
    points. Distributed/asynchronous events belong to protocol
    and Network event infrastructure.
    """

    def __init__(self) -> None:
        self._hooks: dict[str, list[Hook]] = defaultdict(list)
        self._lock = RLock()

    def register(
        self,
        event: str,
        callback: Hook,
    ) -> None:
        if not isinstance(event, str) or not event.strip():
            raise ValueError(
                "Hook event cannot be empty"
            )

        if not callable(callback):
            raise TypeError(
                "Hook callback must be callable"
            )

        with self._lock:
            callbacks = self._hooks[event]

            if callback not in callbacks:
                callbacks.append(callback)

    def unregister(
        self,
        event: str,
        callback: Hook,
    ) -> bool:
        with self._lock:
            callbacks = self._hooks.get(event)

            if not callbacks:
                return False

            if callback not in callbacks:
                return False

            callbacks.remove(callback)

            if not callbacks:
                self._hooks.pop(event, None)

            return True

    def emit(
        self,
        event: str,
        **payload: Any,
    ) -> list[Any]:
        with self._lock:
            callbacks = tuple(
                self._hooks.get(event, ())
            )

        results: list[Any] = []

        for callback in callbacks:
            results.append(
                callback(**payload)
            )

        return results

    def has(
        self,
        event: str,
    ) -> bool:
        with self._lock:
            return bool(
                self._hooks.get(event)
            )

    def events(self) -> tuple[str, ...]:
        with self._lock:
            return tuple(
                sorted(self._hooks)
            )

    def callback_count(
        self,
        event: str,
    ) -> int:
        with self._lock:
            return len(
                self._hooks.get(event, ())
            )

    def clear(
        self,
        event: str | None = None,
    ) -> None:
        with self._lock:
            if event is None:
                self._hooks.clear()
            else:
                self._hooks.pop(event, None)
