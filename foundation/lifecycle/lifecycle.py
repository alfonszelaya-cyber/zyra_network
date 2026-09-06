from __future__ import annotations

from enum import Enum
from threading import RLock


class LifecycleState(str, Enum):
    CREATED = "created"
    INITIALIZED = "initialized"
    RUNNING = "running"
    STOPPED = "stopped"


class LifecycleManager:
    """Controlled lifecycle state machine for foundation components."""

    _TRANSITIONS = {
        LifecycleState.CREATED: {LifecycleState.INITIALIZED},
        LifecycleState.INITIALIZED: {
            LifecycleState.RUNNING,
            LifecycleState.STOPPED,
        },
        LifecycleState.RUNNING: {LifecycleState.STOPPED},
        LifecycleState.STOPPED: set(),
    }

    def __init__(self) -> None:
        self._state = LifecycleState.CREATED
        self._lock = RLock()

    @property
    def state(self) -> LifecycleState:
        with self._lock:
            return self._state

    def transition(self, target: LifecycleState) -> None:
        with self._lock:
            if target not in self._TRANSITIONS[self._state]:
                raise RuntimeError(
                    f"Invalid lifecycle transition: "
                    f"{self._state.value} -> {target.value}"
                )

            self._state = target

    def initialize(self) -> None:
        self.transition(LifecycleState.INITIALIZED)

    def start(self) -> None:
        self.transition(LifecycleState.RUNNING)

    def stop(self) -> None:
        self.transition(LifecycleState.STOPPED)


__all__ = ["LifecycleState", "LifecycleManager"]
