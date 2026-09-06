from __future__ import annotations

import time
from dataclasses import dataclass
from threading import RLock


@dataclass(frozen=True, slots=True)
class DNSCacheEntry:
    hostname: str
    addresses: tuple[str, ...]
    expires_at: float


class DNSCache:
    def __init__(
        self,
        capacity: int = 4096,
    ) -> None:

        if capacity <= 0:
            raise ValueError(
                "capacity must be positive"
            )

        self._capacity = capacity
        self._entries: dict[
            str,
            DNSCacheEntry,
        ] = {}

        self._lock = RLock()

    def put(
        self,
        hostname: str,
        addresses: tuple[str, ...],
        ttl_seconds: float,
    ) -> None:

        if ttl_seconds <= 0:
            raise ValueError(
                "ttl_seconds must be positive"
            )

        entry = DNSCacheEntry(
            hostname=hostname,
            addresses=tuple(addresses),
            expires_at=(
                time.monotonic()
                + ttl_seconds
            ),
        )

        with self._lock:
            if (
                len(self._entries)
                >= self._capacity
                and hostname not in self._entries
            ):
                oldest = min(
                    self._entries,
                    key=lambda key:
                    self._entries[key].expires_at,
                )

                self._entries.pop(
                    oldest
                )

            self._entries[
                hostname
            ] = entry

    def get(
        self,
        hostname: str,
    ) -> tuple[str, ...] | None:

        with self._lock:
            entry = self._entries.get(
                hostname
            )

            if entry is None:
                return None

            if (
                time.monotonic()
                >= entry.expires_at
            ):
                self._entries.pop(
                    hostname,
                    None,
                )

                return None

            return entry.addresses

    def delete(
        self,
        hostname: str,
    ) -> bool:

        with self._lock:
            return (
                self._entries.pop(
                    hostname,
                    None,
                )
                is not None
            )

    def clear(self) -> None:
        with self._lock:
            self._entries.clear()


__all__ = [
    "DNSCache",
    "DNSCacheEntry",
]
