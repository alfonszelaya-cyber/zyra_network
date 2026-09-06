from __future__ import annotations

from enum import StrEnum
from threading import RLock
from typing import Callable


class LifecycleError(RuntimeError):
    """Invalid lifecycle transition."""


class LifecycleState(StrEnum):
    CREATED = "created"
    STARTING = "starting"
    RUNNING = "running"
    STOPPING = "stopping"
    STOPPED = "stopped"
    FAILED = "failed"


LifecycleCallback = Callable[[], None]


class Lifecycle:
    """
    Deterministic component lifecycle controller.

    State transitions are serialized and callbacks execute only
    after the corresponding transition is accepted.
    """

    _ALLOWED: dict[
        LifecycleState,
        frozenset[LifecycleState],
    ] = {
        LifecycleState.CREATED: frozenset({
            LifecycleState.STARTING,
            LifecycleState.FAILED,
        }),
        LifecycleState.STARTING: frozenset({
            LifecycleState.RUNNING,
            LifecycleState.FAILED,
        }),
        LifecycleState.RUNNING: frozenset({
            LifecycleState.STOPPING,
            LifecycleState.FAILED,
        }),
        LifecycleState.STOPPING: frozenset({
            LifecycleState.STOPPED,
            LifecycleState.FAILED,
        }),
        LifecycleState.STOPPED: frozenset(),
        LifecycleState.FAILED: frozenset(),
    }

    def __init__(self) -> None:
        self._state = LifecycleState.CREATED
        self._lock = RLock()
        self._callbacks: dict[
            LifecycleState,
            list[LifecycleCallback],
        ] = {
            state: []
            for state in LifecycleState
        }

    @property
    def state(self) -> LifecycleState:
        with self._lock:
            return self._state

    def transition(
        self,
        target: LifecycleState,
    ) -> LifecycleState:
        with self._lock:
            if target == self._state:
                return self._state

            allowed = self._ALLOWED[
                self._state
            ]

            if target not in allowed:
                raise LifecycleError(
                    f"Invalid lifecycle transition: "
                    f"{self._state} -> {target}"
                )

            self._state = target
            callbacks = tuple(
                self._callbacks[target]
            )

        for callback in callbacks:
            callback()

        return target

    def on(
        self,
        state: LifecycleState,
        callback: LifecycleCallback,
    ) -> None:
        if not callable(callback):
            raise TypeError(
                "Lifecycle callback must be callable"
            )

        with self._lock:
            self._callbacks[state].append(
                callback
            )

    def start(self) -> LifecycleState:
        self.transition(
            LifecycleState.STARTING
        )
        return self.transition(
            LifecycleState.RUNNING
        )

    def stop(self) -> LifecycleState:
        self.transition(
            LifecycleState.STOPPING
        )
        return self.transition(
            LifecycleState.STOPPED
        )

    def fail(self) -> LifecycleState:
        return self.transition(
            LifecycleState.FAILED
        )
