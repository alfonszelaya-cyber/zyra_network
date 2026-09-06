from __future__ import annotations

from collections import deque
from threading import Condition, RLock
from typing import Generic, TypeVar


T = TypeVar("T")


class MessageQueue(Generic[T]):
    def __init__(
        self,
        max_size: int = 10000,
    ) -> None:

        if max_size <= 0:
            raise ValueError(
                "max_size must be positive"
            )

        self._queue: deque[T] = deque()
        self._max_size = max_size
        self._lock = RLock()
        self._condition = Condition(
            self._lock
        )
        self._closed = False

    def put(
        self,
        item: T,
        *,
        block: bool = True,
        timeout: float | None = None,
    ) -> None:

        with self._condition:
            if self._closed:
                raise RuntimeError(
                    "Message queue is closed"
                )

            if not block:
                if len(self._queue) >= self._max_size:
                    raise OverflowError(
                        "Message queue is full"
                    )
            else:
                if not self._condition.wait_for(
                    lambda: (
                        len(self._queue)
                        < self._max_size
                        or self._closed
                    ),
                    timeout=timeout,
                ):
                    raise TimeoutError(
                        "Timed out waiting for queue capacity"
                    )

                if self._closed:
                    raise RuntimeError(
                        "Message queue is closed"
                    )

            self._queue.append(item)
            self._condition.notify_all()

    def get(
        self,
        *,
        block: bool = True,
        timeout: float | None = None,
    ) -> T:

        with self._condition:
            if not block:
                if not self._queue:
                    raise LookupError(
                        "Message queue is empty"
                    )
            else:
                if not self._condition.wait_for(
                    lambda: (
                        bool(self._queue)
                        or self._closed
                    ),
                    timeout=timeout,
                ):
                    raise TimeoutError(
                        "Timed out waiting for message"
                    )

                if not self._queue:
                    raise LookupError(
                        "Message queue is empty"
                    )

            item = self._queue.popleft()
            self._condition.notify_all()
            return item

    def size(self) -> int:
        with self._lock:
            return len(self._queue)

    def clear(self) -> int:
        with self._condition:
            count = len(self._queue)
            self._queue.clear()
            self._condition.notify_all()
            return count

    def close(self) -> None:
        with self._condition:
            self._closed = True
            self._condition.notify_all()

    @property
    def closed(self) -> bool:
        with self._lock:
            return self._closed


__all__ = ["MessageQueue"]
