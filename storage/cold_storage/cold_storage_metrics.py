from __future__ import annotations

from dataclasses import dataclass
from threading import RLock


@dataclass(frozen=True, slots=True)
class ColdStorageMetricsSnapshot:
    writes: int
    reads: int
    deletes: int
    bytes_written: int
    bytes_read: int


class ColdStorageMetrics:
    def __init__(self) -> None:
        self._writes = 0
        self._reads = 0
        self._deletes = 0
        self._bytes_written = 0
        self._bytes_read = 0

        self._lock = RLock()

    def record_write(
        self,
        size_bytes: int,
    ) -> None:

        if size_bytes < 0:
            raise ValueError(
                "size_bytes cannot be negative"
            )

        with self._lock:
            self._writes += 1
            self._bytes_written += size_bytes

    def record_read(
        self,
        size_bytes: int,
    ) -> None:

        if size_bytes < 0:
            raise ValueError(
                "size_bytes cannot be negative"
            )

        with self._lock:
            self._reads += 1
            self._bytes_read += size_bytes

    def record_delete(self) -> None:
        with self._lock:
            self._deletes += 1

    def snapshot(
        self,
    ) -> ColdStorageMetricsSnapshot:

        with self._lock:
            return ColdStorageMetricsSnapshot(
                writes=self._writes,
                reads=self._reads,
                deletes=self._deletes,
                bytes_written=self._bytes_written,
                bytes_read=self._bytes_read,
            )


__all__ = [
    "ColdStorageMetrics",
    "ColdStorageMetricsSnapshot",
]
