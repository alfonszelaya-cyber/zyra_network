from __future__ import annotations

from dataclasses import dataclass
from threading import RLock


@dataclass(frozen=True, slots=True)
class MessageMetricsSnapshot:
    published: int
    delivered: int
    failed: int
    rejected: int

    @property
    def total_processed(self) -> int:
        return (
            self.delivered
            + self.failed
            + self.rejected
        )


class MessageMetrics:
    def __init__(self) -> None:
        self._published = 0
        self._delivered = 0
        self._failed = 0
        self._rejected = 0
        self._lock = RLock()

    def record_published(self) -> None:
        with self._lock:
            self._published += 1

    def record_delivered(self) -> None:
        with self._lock:
            self._delivered += 1

    def record_failed(self) -> None:
        with self._lock:
            self._failed += 1

    def record_rejected(self) -> None:
        with self._lock:
            self._rejected += 1

    def snapshot(
        self,
    ) -> MessageMetricsSnapshot:

        with self._lock:
            return MessageMetricsSnapshot(
                published=self._published,
                delivered=self._delivered,
                failed=self._failed,
                rejected=self._rejected,
            )

    def reset(self) -> None:
        with self._lock:
            self._published = 0
            self._delivered = 0
            self._failed = 0
            self._rejected = 0


__all__ = [
    "MessageMetrics",
    "MessageMetricsSnapshot",
]
