from __future__ import annotations

import signal
from dataclasses import dataclass
from enum import Enum
from threading import Event, RLock
from time import monotonic


class RuntimeState(str, Enum):
    CREATED = "created"
    STARTING = "starting"
    RUNNING = "running"
    STOPPING = "stopping"
    STOPPED = "stopped"
    FAILED = "failed"


class RuntimeErrorState(RuntimeError):
    """Raised for invalid runtime lifecycle transitions."""


@dataclass(frozen=True, slots=True)
class RuntimeSnapshot:
    state: RuntimeState
    started_at: float | None
    stopped_at: float | None
    stop_requested: bool


class Runtime:
    """
    Process lifecycle coordinator.
    """

    def __init__(
        self,
        *,
        shutdown_timeout_seconds: int = 30,
    ) -> None:

        if shutdown_timeout_seconds < 0:
            raise ValueError(
                "shutdown_timeout_seconds cannot be negative"
            )

        self.shutdown_timeout_seconds = (
            shutdown_timeout_seconds
        )

        self._state = (
            RuntimeState.CREATED
        )

        self._started_at: float | None = None
        self._stopped_at: float | None = None

        self._stop_event = Event()
        self._lock = RLock()

        self._startup_hooks: list = []
        self._shutdown_hooks: list = []

        self._signals_installed = False

    def on_start(
        self,
        callback,
    ) -> None:

        if not callable(callback):
            raise TypeError(
                "Startup callback must be callable"
            )

        with self._lock:
            self._startup_hooks.append(
                callback
            )

    def on_shutdown(
        self,
        callback,
    ) -> None:

        if not callable(callback):
            raise TypeError(
                "Shutdown callback must be callable"
            )

        with self._lock:
            self._shutdown_hooks.append(
                callback
            )

    def install_signal_handlers(
        self,
    ) -> None:

        with self._lock:
            if self._signals_installed:
                return

            signal.signal(
                signal.SIGTERM,
                self._signal_handler,
            )

            signal.signal(
                signal.SIGINT,
                self._signal_handler,
            )

            self._signals_installed = True

    def _signal_handler(
        self,
        signum,
        _frame,
    ) -> None:

        self.request_shutdown()

    def start(self) -> None:

        with self._lock:
            if self._state is RuntimeState.RUNNING:
                return

            if self._state not in {
                RuntimeState.CREATED,
                RuntimeState.STOPPED,
            }:
                raise RuntimeErrorState(
                    f"Cannot start runtime from "
                    f"{self._state.value}"
                )

            self._state = (
                RuntimeState.STARTING
            )

        try:
            for callback in tuple(
                self._startup_hooks
            ):
                callback()

            with self._lock:
                self._started_at = monotonic()
                self._stopped_at = None
                self._stop_event.clear()

                self._state = (
                    RuntimeState.RUNNING
                )

        except BaseException:
            with self._lock:
                self._state = (
                    RuntimeState.FAILED
                )

            raise

    def request_shutdown(self) -> None:
        self._stop_event.set()

    def wait_for_shutdown(
        self,
        timeout: float | None = None,
    ) -> bool:

        return self._stop_event.wait(
            timeout
        )

    def stop(self) -> None:

        with self._lock:
            if self._state is RuntimeState.STOPPED:
                return

            if self._state is RuntimeState.CREATED:
                self._state = (
                    RuntimeState.STOPPED
                )
                self._stopped_at = monotonic()
                return

            if self._state is RuntimeState.FAILED:
                self._state = (
                    RuntimeState.STOPPING
                )
            elif self._state is RuntimeState.RUNNING:
                self._state = (
                    RuntimeState.STOPPING
                )
            elif self._state is RuntimeState.STOPPING:
                return
            else:
                raise RuntimeErrorState(
                    f"Cannot stop runtime from "
                    f"{self._state.value}"
                )

        errors: list[BaseException] = []

        for callback in reversed(
            tuple(self._shutdown_hooks)
        ):
            try:
                callback()
            except BaseException as exc:
                errors.append(exc)

        with self._lock:
            self._stopped_at = monotonic()
            self._state = (
                RuntimeState.STOPPED
            )

        if errors:
            raise RuntimeErrorState(
                f"{len(errors)} shutdown hook(s) failed"
            )

    def snapshot(
        self,
    ) -> RuntimeSnapshot:

        with self._lock:
            return RuntimeSnapshot(
                state=self._state,
                started_at=self._started_at,
                stopped_at=self._stopped_at,
                stop_requested=(
                    self._stop_event.is_set()
                ),
            )

    @property
    def state(self) -> RuntimeState:
        with self._lock:
            return self._state

    @property
    def running(self) -> bool:
        return (
            self.state
            is RuntimeState.RUNNING
        )


__all__ = [
    "Runtime",
    "RuntimeErrorState",
    "RuntimeSnapshot",
    "RuntimeState",
]
