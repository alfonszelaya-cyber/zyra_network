from __future__ import annotations

from collections.abc import Callable
from threading import RLock
from typing import Any


Hook = Callable[..., Any]


class HookRegistry:
    """Thread-safe registry for lifecycle and system extension hooks."""

    def __init__(self) -> None:
        self._hooks: dict[str, list[Hook]] = {}
        self._lock = RLock()

    def register(self, event: str, hook: Hook) -> None:
        if not event or not event.strip():
            raise ValueError("Hook event cannot be empty")

        if not callable(hook):
            raise TypeError("Hook must be callable")

        normalized = event.strip()

        with self._lock:
            hooks = self._hooks.setdefault(normalized, [])
            if hook not in hooks:
                hooks.append(hook)

    def unregister(self, event: str, hook: Hook) -> bool:
        with self._lock:
            hooks = self._hooks.get(event.strip())

            if not hooks or hook not in hooks:
                return False

            hooks.remove(hook)

            if not hooks:
                self._hooks.pop(event.strip(), None)

            return True

    def emit(self, event: str, *args: Any, **kwargs: Any) -> list[Any]:
        with self._lock:
            hooks = tuple(self._hooks.get(event.strip(), ()))

        results: list[Any] = []

        for hook in hooks:
            results.append(hook(*args, **kwargs))

        return results

    def has(self, event: str) -> bool:
        with self._lock:
            return bool(self._hooks.get(event.strip()))

    def clear(self, event: str | None = None) -> None:
        with self._lock:
            if event is None:
                self._hooks.clear()
            else:
                self._hooks.pop(event.strip(), None)

    def events(self) -> tuple[str, ...]:
        with self._lock:
            return tuple(sorted(self._hooks))


__all__ = ["Hook", "HookRegistry"]
