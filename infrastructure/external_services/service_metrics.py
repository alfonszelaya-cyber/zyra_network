from __future__ import annotations

from dataclasses import dataclass
from threading import RLock


@dataclass(frozen=True, slots=True)
class ServiceMetricsSnapshot:
    requests: int
    successes: int
    failures: int
    timeouts: int
    bytes_sent: int
    bytes_received: int


class ServiceMetrics:
    def __init__(self) -> None:
        self._requests = 0
        self._successes = 0
        self._failures = 0
        self._timeouts = 0
        self._bytes_sent = 0
        self._bytes_received = 0
        self._lock = RLock()

    def record_request(
        self,
        *,
        bytes_sent: int = 0,
    ) -> None:

        if bytes_sent < 0:
            raise ValueError(
                "bytes_sent cannot be negative"
            )

        with self._lock:
            self._requests += 1
            self._bytes_sent += bytes_sent

    def record_success(
        self,
        *,
        bytes_received: int = 0,
    ) -> None:

        if bytes_received < 0:
            raise ValueError(
                "bytes_received cannot be negative"
            )

        with self._lock:
            self._successes += 1
            self._bytes_received += (
                bytes_received
            )

    def record_failure(self) -> None:
        with self._lock:
            self._failures += 1

    def record_timeout(self) -> None:
        with self._lock:
            self._timeouts += 1

    def snapshot(
        self,
    ) -> ServiceMetricsSnapshot:

        with self._lock:
            return ServiceMetricsSnapshot(
                requests=self._requests,
                successes=self._successes,
                failures=self._failures,
                timeouts=self._timeouts,
                bytes_sent=self._bytes_sent,
                bytes_received=self._bytes_received,
            )


__all__ = [
    "ServiceMetrics",
    "ServiceMetricsSnapshot",
]
