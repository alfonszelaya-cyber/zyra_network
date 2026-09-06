"""
Deterministic due-task scheduler.

Execution is deliberately delegated to callbacks so this layer
can later be backed by a distributed scheduler without changing
its public contract.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from threading import RLock
from typing import Callable


@dataclass(frozen=True, slots=True)
class SecuritySchedule:
    task_id: str
    run_at: datetime
    callback: Callable[
        [],
        object,
    ]
    enabled: bool = True

    def __post_init__(self) -> None:
        if not self.task_id.strip():
            raise ValueError(
                "task_id is required"
            )

        if self.run_at.tzinfo is None:
            raise ValueError(
                "run_at must be timezone-aware"
            )

        if not callable(
            self.callback
        ):
            raise TypeError(
                "callback must be callable"
            )


class SecurityScheduler:
    """Thread-safe one-shot security task scheduler."""

    def __init__(self) -> None:
        self._tasks: dict[
            str,
            SecuritySchedule,
        ] = {}

        self._lock = RLock()

    def schedule(
        self,
        task_id: str,
        run_at: datetime,
        callback: Callable[
            [],
            object,
        ],
    ) -> SecuritySchedule:
        item = SecuritySchedule(
            task_id=task_id,
            run_at=run_at,
            callback=callback,
        )

        with self._lock:
            if task_id in self._tasks:
                raise ValueError(
                    f"security task already exists: "
                    f"{task_id}"
                )

            self._tasks[
                task_id
            ] = item

        return item

    def cancel(
        self,
        task_id: str,
    ) -> None:
        with self._lock:
            self._tasks.pop(
                task_id,
                None,
            )

    def due(
        self,
        now: datetime | None = None,
    ) -> tuple[
        SecuritySchedule,
        ...,
    ]:
        current = (
            now
            or datetime.now(
                timezone.utc
            )
        )

        if current.tzinfo is None:
            raise ValueError(
                "now must be timezone-aware"
            )

        with self._lock:
            return tuple(
                task
                for task
                in self._tasks.values()
                if (
                    task.enabled
                    and task.run_at
                    <= current
                )
            )

    def run_due(
        self,
        now: datetime | None = None,
    ) -> int:
        tasks = self.due(now)
        executed = 0

        for task in tasks:
            task.callback()
            executed += 1
            self.cancel(
                task.task_id
            )

        return executed


__all__ = [
    "SecuritySchedule",
    "SecurityScheduler",
]
