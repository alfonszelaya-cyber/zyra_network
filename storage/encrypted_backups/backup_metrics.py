from __future__ import annotations

from dataclasses import dataclass
from threading import RLock


@dataclass(frozen=True, slots=True)
class BackupMetricsSnapshot:
    created: int
    restored: int
    failed: int
    bytes_written: int
    bytes_restored: int


class BackupMetrics:
    def __init__(self) -> None:
        self._created = 0
        self._restored = 0
        self._failed = 0
        self._bytes_written = 0
        self._bytes_restored = 0

        self._lock = RLock()

    def record_created(
        self,
        size_bytes: int,
    ) -> None:

        with self._lock:
            self._created += 1
            self._bytes_written += size_bytes

    def record_restored(
        self,
        size_bytes: int,
    ) -> None:

        with self._lock:
            self._restored += 1
            self._bytes_restored += size_bytes

    def record_failed(self) -> None:
        with self._lock:
            self._failed += 1

    def snapshot(
        self,
    ) -> BackupMetricsSnapshot:

        with self._lock:
            return BackupMetricsSnapshot(
                created=self._created,
                restored=self._restored,
                failed=self._failed,
                bytes_written=self._bytes_written,
                bytes_restored=self._bytes_restored,
            )


__all__ = [
    "BackupMetrics",
    "BackupMetricsSnapshot",
]
