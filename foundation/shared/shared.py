from __future__ import annotations

from collections.abc import Iterator, Mapping
from contextlib import contextmanager
from threading import RLock
from typing import Any


class SharedContext:
    """Thread-safe key/value context for explicitly shared foundation data."""

    def __init__(
        self,
        initial: Mapping[str, Any] | None = None,
    ) -> None:
        self._values: dict[str, Any] = dict(initial or {})
        self._lock = RLock()

    def set(self, key: str, value: Any) -> None:
        normalized = key.strip()

        if not normalized:
            raise ValueError("Shared context key cannot be empty")

        with self._lock:
            self._values[normalized] = value

    def get(self, key: str, default: Any = None) -> Any:
        with self._lock:
            return self._values.get(key, default)

    def require(self, key: str) -> Any:
        with self._lock:
            if key not in self._values:
                raise KeyError(key)
            return self._values[key]

    def remove(self, key: str) -> Any:
        with self._lock:
            return self._values.pop(key)

    def contains(self, key: str) -> bool:
        with self._lock:
            return key in self._values

    def snapshot(self) -> dict[str, Any]:
        with self._lock:
            return dict(self._values)

    def __len__(self) -> int:
        with self._lock:
            return len(self._values)

    def __iter__(self) -> Iterator[str]:
        return iter(self.snapshot())


@contextmanager
def temporary_value(
    context: SharedContext,
    key: str,
    value: Any,
):
    marker = object()
    previous = context.get(key, marker)
    context.set(key, value)

    try:
        yield context
    finally:
        if previous is marker:
            try:
                context.remove(key)
            except KeyError:
                pass
        else:
            context.set(key, previous)


__all__ = ["SharedContext", "temporary_value"]
