"""Pluggable metrics and logging backends.

Engines depend only on these protocols; OpenTelemetry or
Prometheus adapters plug in at the composition root without
touching domain code.
"""
from __future__ import annotations

import logging
import threading
from collections.abc import Mapping, Sequence
from typing import Protocol

TagMap = Mapping[str, str] | None


class MetricsBackend(Protocol):
    def increment(self, name: str, *, tags: TagMap = None) -> None:
        ...

    def observe(self, name: str, value: float, *, tags: TagMap = None) -> None:
        ...


class NoopMetrics:
    """Discards metrics; default when no backend is configured."""

    def increment(self, name: str, *, tags: TagMap = None) -> None:
        return None

    def observe(self, name: str, value: float, *, tags: TagMap = None) -> None:
        return None


class InMemoryMetrics:
    """Thread-safe backend for tests and local introspection."""

    def __init__(self) -> None:
        self._lock = threading.Lock()
        self._counters: dict[
            tuple[str, tuple[tuple[str, str], ...]], int
        ] = {}
        self._series: dict[str, list[float]] = {}

    def increment(self, name: str, *, tags: TagMap = None) -> None:
        key = (name, tuple(sorted((tags or {}).items())))
        with self._lock:
            self._counters[key] = self._counters.get(key, 0) + 1

    def observe(self, name: str, value: float, *, tags: TagMap = None) -> None:
        with self._lock:
            series = self._series.setdefault(name, [])
            series.append(value)

    def counter_value(self, name: str, tags: TagMap = None) -> int:
        key = (name, tuple(sorted((tags or {}).items())))
        with self._lock:
            return self._counters.get(key, 0)

    def values(self, name: str) -> tuple[float, ...]:
        with self._lock:
            return tuple(self._series.get(name, ()))


class CompositeMetrics:
    """Fans out to several registered backends."""

    def __init__(self, backends: Sequence[MetricsBackend]) -> None:
        self._backends = tuple(backends)

    def increment(self, name: str, *, tags: TagMap = None) -> None:
        for backend in self._backends:
            backend.increment(name, tags=tags)

    def observe(self, name: str, value: float, *, tags: TagMap = None) -> None:
        for backend in self._backends:
            backend.observe(name, value, tags=tags)


def engine_logger(engine: str) -> logging.Logger:
    """Namespaced logger; call sites log ids and kinds only."""
    return logging.getLogger(f"zyra.shared_engines.{engine}")
