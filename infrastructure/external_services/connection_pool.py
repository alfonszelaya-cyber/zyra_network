from __future__ import annotations

from dataclasses import dataclass
from threading import Condition, RLock
from typing import Generic, TypeVar


T = TypeVar("T")


@dataclass(frozen=True, slots=True)
class PoolStats:
    created: int
    acquired: int
    released: int
    available: int
    closed: bool


class ConnectionPool(Generic[T]):
    def __init__(
        self,
        factory,
        *,
        max_size: int = 32,
    ) -> None:

        if max_size <= 0:
            raise ValueError(
                "max_size must be positive"
            )

        if not callable(factory):
            raise TypeError(
                "Connection factory must be callable"
            )

        self._factory = factory
        self._max_size = max_size
        self._available: list[T] = []
        self._created = 0
        self._acquired = 0
        self._released = 0
        self._closed = False

        self._lock = RLock()
        self._condition = Condition(
            self._lock
        )

    def acquire(
        self,
        *,
        timeout: float | None = None,
    ) -> T:

        with self._condition:
            if self._closed:
                raise RuntimeError(
                    "Connection pool is closed"
                )

            if self._available:
                connection = (
                    self._available.pop()
                )

                self._acquired += 1

                return connection

            if (
                self._created
                < self._max_size
            ):
                connection = self._factory()

                if connection is None:
                    raise RuntimeError(
                        "Connection factory returned None"
                    )

                self._created += 1
                self._acquired += 1

                return connection

            if not self._condition.wait_for(
                lambda: (
                    bool(self._available)
                    or self._closed
                ),
                timeout=timeout,
            ):
                raise TimeoutError(
                    "Timed out waiting for pooled connection"
                )

            if self._closed:
                raise RuntimeError(
                    "Connection pool is closed"
                )

            connection = (
                self._available.pop()
            )

            self._acquired += 1

            return connection

    def release(
        self,
        connection: T,
    ) -> None:

        if connection is None:
            raise ValueError(
                "Cannot release None connection"
            )

        with self._condition:
            if self._closed:
                close = getattr(
                    connection,
                    "close",
                    None,
                )

                if callable(close):
                    close()

                return

            self._available.append(
                connection
            )

            self._released += 1
            self._condition.notify()

    def stats(self) -> PoolStats:
        with self._lock:
            return PoolStats(
                created=self._created,
                acquired=self._acquired,
                released=self._released,
                available=len(
                    self._available
                ),
                closed=self._closed,
            )

    def close(self) -> None:
        with self._condition:
            if self._closed:
                return

            self._closed = True
            connections = tuple(
                self._available
            )

            self._available.clear()
            self._condition.notify_all()

        errors: list[BaseException] = []

        for connection in connections:
            close = getattr(
                connection,
                "close",
                None,
            )

            if callable(close):
                try:
                    close()
                except BaseException as exc:
                    errors.append(exc)

        if errors:
            raise RuntimeError(
                f"{len(errors)} pooled connection close operation(s) failed"
            )


__all__ = [
    "ConnectionPool",
    "PoolStats",
]
