from __future__ import annotations

from dataclasses import dataclass
from threading import RLock


@dataclass(frozen=True, slots=True)
class ShardMetricsSnapshot:
    writes: int
    reads: int
    deletes: int
    rebalances: int


class ShardMetrics:
    def __init__(self) -> None:
        self._writes = 0
        self._reads = 0
        self._deletes = 0
        self._rebalances = 0

        self._lock = RLock()

    def record_write(self) -> None:
        with self._lock:
            self._writes += 1

    def record_read(self) -> None:
        with self._lock:
            self._reads += 1

    def record_delete(self) -> None:
        with self._lock:
            self._deletes += 1

    def record_rebalance(self) -> None:
        with self._lock:
            self._rebalances += 1

    def snapshot(
        self,
    ) -> ShardMetricsSnapshot:

        with self._lock:
            return ShardMetricsSnapshot(
                writes=self._writes,
                reads=self._reads,
                deletes=self._deletes,
                rebalances=self._rebalances,
            )


__all__ = [
    "ShardMetrics",
    "ShardMetricsSnapshot",
]
