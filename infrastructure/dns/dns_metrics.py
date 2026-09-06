from __future__ import annotations

from dataclasses import dataclass
from threading import RLock


@dataclass(frozen=True, slots=True)
class DNSMetricsSnapshot:
    lookups: int
    cache_hits: int
    cache_misses: int
    failures: int


class DNSMetrics:
    def __init__(self) -> None:
        self._lookups = 0
        self._cache_hits = 0
        self._cache_misses = 0
        self._failures = 0
        self._lock = RLock()

    def record_lookup(self) -> None:
        with self._lock:
            self._lookups += 1

    def record_cache_hit(self) -> None:
        with self._lock:
            self._cache_hits += 1

    def record_cache_miss(self) -> None:
        with self._lock:
            self._cache_misses += 1

    def record_failure(self) -> None:
        with self._lock:
            self._failures += 1

    def snapshot(
        self,
    ) -> DNSMetricsSnapshot:

        with self._lock:
            return DNSMetricsSnapshot(
                lookups=self._lookups,
                cache_hits=self._cache_hits,
                cache_misses=self._cache_misses,
                failures=self._failures,
            )


__all__ = [
    "DNSMetrics",
    "DNSMetricsSnapshot",
]
