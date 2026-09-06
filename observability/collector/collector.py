from __future__ import annotations

import threading
from collections import deque
from typing import Any

from ..core import (
    ObservationEvent,
    ObservationManager,
)


class SignalCollector:
    def __init__(
        self,
        manager: ObservationManager,
        *,
        max_queue: int = 10_000,
    ) -> None:

        if max_queue <= 0:
            raise ValueError(
                "max_queue must be positive"
            )

        self.manager = manager
        self._queue: deque[Any] = deque(
            maxlen=max_queue
        )
        self._dropped = 0
        self._lock = threading.RLock()

    def submit(
        self,
        signal: Any,
    ) -> bool:

        with self._lock:
            if len(self._queue) == self._queue.maxlen:
                self._dropped += 1
                return False

            self._queue.append(signal)
            return True

    def drain(
        self,
        limit: int = 1_000,
    ) -> int:

        processed = 0

        while processed < limit:
            with self._lock:
                if not self._queue:
                    break

                signal = self._queue.popleft()

            if isinstance(
                signal,
                ObservationEvent,
            ):
                self.manager.record_event(
                    signal
                )

            processed += 1

        return processed

    def pending(self) -> int:
        with self._lock:
            return len(self._queue)

    def dropped(self) -> int:
        with self._lock:
            return self._dropped


__all__ = ["SignalCollector"]
