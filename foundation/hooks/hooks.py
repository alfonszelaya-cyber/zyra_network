from __future__ import annotations

from collections import defaultdict
from threading import RLock
from typing import Any, Callable


Hook = Callable[..., Any]


class HookRegistry:
    """
    Thread-safe lifecycle/event hook registry.

    Hooks are intentionally synchronous at this foundation layer.
    Async orchestration belongs to the Network event subsystem.
    """

    def __init__(self) -> None:
        self._hooks: dict[str, list[Hook]] = defaultdict(list)
        self._lock = RLock()

    def register(
        self,
        event: str,
        callback: Hook,
    ) -> None:
        if not event.strip():
            raise ValueError("event cannot be empty")

        if not callable(callback):
            raise TypeError("callback must be callable")

        with self._lock:
            if callback not in self._hooks[event]:
                self._hooks[event].append(callback)

    def unregister(
        self,
        event: str,
        callback: Hook,
    ) -> None:
        with self._lock:
            callbacks = self._hooks.get(event)

            if not callbacks:
                return

            if callback in callbacks:
                callbacks.remove(callback)

            if not callbacks:
                self._hooks.pop(event, None)

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
            results.append(callback(**payload))

        return results

    def events(self) -> tuple[str, ...]:
        with self._lock:
            return tuple(sorted(self._hooks))

    def clear(self) -> None:
        with self._lock:
            self._hooks.clear()
