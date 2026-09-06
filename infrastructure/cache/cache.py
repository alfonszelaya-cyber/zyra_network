from __future__ import annotations

import time
from collections import OrderedDict
from dataclasses import dataclass
from threading import RLock
from typing import Generic, TypeVar


T = TypeVar("T")


@dataclass(frozen=True, slots=True)
class CacheEntry(Generic[T]):
    value: T
    expires_at: float | None


@dataclass(frozen=True, slots=True)
class CacheStats:
    hits: int
    misses: int
    evictions: int
    expirations: int
    size: int
    capacity: int

    @property
    def hit_ratio(self) -> float:
        total = self.hits + self.misses

        if total == 0:
            return 0.0

        return self.hits / total


class Cache(Generic[T]):
    """
    Thread-safe bounded LRU cache with TTL.

    Cache is never the source of truth for durable state.
    """

    def __init__(
        self,
        capacity: int = 4096,
        default_ttl_seconds: int = 300,
    ) -> None:

        if capacity <= 0:
            raise ValueError(
                "capacity must be positive"
            )

        if default_ttl_seconds <= 0:
            raise ValueError(
                "default_ttl_seconds must be positive"
            )

        self._capacity = capacity
        self._default_ttl = (
            default_ttl_seconds
        )

        self._entries: OrderedDict[
            str,
            CacheEntry[T],
        ] = OrderedDict()

        self._hits = 0
        self._misses = 0
        self._evictions = 0
        self._expirations = 0

        self._lock = RLock()
        self._closed = False

    def _require_open(self) -> None:
        if self._closed:
            raise RuntimeError(
                "Cache is closed"
            )

    @staticmethod
    def _expiration(
        ttl_seconds: int | None,
    ) -> float | None:

        if ttl_seconds is None:
            return None

        if ttl_seconds <= 0:
            raise ValueError(
                "ttl_seconds must be positive"
            )

        return (
            time.monotonic()
            + ttl_seconds
        )

    @staticmethod
    def _expired(
        entry: CacheEntry[T],
    ) -> bool:

        return (
            entry.expires_at is not None
            and time.monotonic()
            >= entry.expires_at
        )

    def set(
        self,
        key: str,
        value: T,
        *,
        ttl_seconds: int | None = None,
    ) -> None:

        key = key.strip()

        if not key:
            raise ValueError(
                "Cache key cannot be empty"
            )

        with self._lock:
            self._require_open()

            self._entries.pop(
                key,
                None,
            )

            ttl = (
                self._default_ttl
                if ttl_seconds is None
                else ttl_seconds
            )

            self._entries[key] = CacheEntry(
                value=value,
                expires_at=self._expiration(
                    ttl
                ),
            )

            while (
                len(self._entries)
                > self._capacity
            ):
                self._entries.popitem(
                    last=False
                )

                self._evictions += 1

    def get(
        self,
        key: str,
        default: T | None = None,
    ) -> T | None:

        key = key.strip()

        if not key:
            raise ValueError(
                "Cache key cannot be empty"
            )

        with self._lock:
            self._require_open()

            entry = self._entries.get(
                key
            )

            if entry is None:
                self._misses += 1
                return default

            if self._expired(entry):
                self._entries.pop(
                    key,
                    None,
                )

                self._misses += 1
                self._expirations += 1

                return default

            self._entries.move_to_end(
                key
            )

            self._hits += 1

            return entry.value

    def get_or_set(
        self,
        key: str,
        factory,
        *,
        ttl_seconds: int | None = None,
    ) -> T:

        existing = self.get(
            key,
            None,
        )

        if existing is not None:
            return existing

        value = factory()

        if value is None:
            raise ValueError(
                "Cache factory cannot return None"
            )

        self.set(
            key,
            value,
            ttl_seconds=ttl_seconds,
        )

        return value

    def delete(
        self,
        key: str,
    ) -> bool:

        key = key.strip()

        if not key:
            raise ValueError(
                "Cache key cannot be empty"
            )

        with self._lock:
            self._require_open()

            return (
                self._entries.pop(
                    key,
                    None,
                )
                is not None
            )

    def exists(
        self,
        key: str,
    ) -> bool:

        sentinel = object()

        return (
            self.get(
                key,
                sentinel,
            )
            is not sentinel
        )

    def clear(self) -> None:
        with self._lock:
            self._require_open()
            self._entries.clear()

    def cleanup_expired(self) -> int:
        with self._lock:
            self._require_open()

            expired = [
                key
                for key, entry
                in self._entries.items()
                if self._expired(entry)
            ]

            for key in expired:
                self._entries.pop(
                    key,
                    None,
                )

            self._expirations += len(
                expired
            )

            return len(expired)

    def stats(self) -> CacheStats:
        with self._lock:
            return CacheStats(
                hits=self._hits,
                misses=self._misses,
                evictions=self._evictions,
                expirations=self._expirations,
                size=len(self._entries),
                capacity=self._capacity,
            )

    def close(self) -> None:
        with self._lock:
            if self._closed:
                return

            self._entries.clear()
            self._closed = True

    @property
    def closed(self) -> bool:
        with self._lock:
            return self._closed


__all__ = [
    "Cache",
    "CacheEntry",
    "CacheStats",
]
