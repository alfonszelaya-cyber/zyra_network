from __future__ import annotations

from dataclasses import dataclass
from threading import RLock
from typing import Any, Callable


class KernelError(RuntimeError):
    """Base kernel failure."""


class KernelNotRunningError(KernelError):
    """Operation requires a running kernel."""


KernelHandler = Callable[..., Any]


@dataclass(frozen=True, slots=True)
class KernelState:
    name: str
    running: bool
    generation: int


class Kernel:
    """
    Minimal ZYRA execution kernel.

    The kernel coordinates registered handlers and exposes the
    fundamental execution boundary. Network transports, storage,
    messaging and applications remain outside this primitive.
    """

    def __init__(
        self,
        *,
        name: str = "zyra-kernel",
    ) -> None:
        if not name.strip():
            raise ValueError(
                "Kernel name cannot be empty"
            )

        self._name = name
        self._running = False
        self._generation = 0
        self._handlers: dict[str, KernelHandler] = {}
        self._lock = RLock()

    @property
    def name(self) -> str:
        return self._name

    @property
    def running(self) -> bool:
        with self._lock:
            return self._running

    @property
    def generation(self) -> int:
        with self._lock:
            return self._generation

    def start(self) -> KernelState:
        with self._lock:
            if self._running:
                return self.state()

            self._generation += 1
            self._running = True

            return self.state()

    def stop(self) -> KernelState:
        with self._lock:
            if not self._running:
                return self.state()

            self._running = False

            return self.state()

    def state(self) -> KernelState:
        return KernelState(
            name=self._name,
            running=self._running,
            generation=self._generation,
        )

    def register(
        self,
        name: str,
        handler: KernelHandler,
    ) -> None:
        if not name.strip():
            raise ValueError(
                "Handler name cannot be empty"
            )

        if not callable(handler):
            raise TypeError(
                "Kernel handler must be callable"
            )

        with self._lock:
            if name in self._handlers:
                raise KernelError(
                    f"Handler already registered: {name}"
                )

            self._handlers[name] = handler

    def unregister(self, name: str) -> bool:
        with self._lock:
            return (
                self._handlers.pop(
                    name,
                    None,
                )
                is not None
            )

    def execute(
        self,
        name: str,
        *args: Any,
        **kwargs: Any,
    ) -> Any:
        with self._lock:
            if not self._running:
                raise KernelNotRunningError(
                    "Kernel is not running"
                )

            handler = self._handlers.get(name)

            if handler is None:
                raise KernelError(
                    f"Unknown kernel handler: {name}"
                )

        return handler(
            *args,
            **kwargs,
        )

    def handlers(self) -> tuple[str, ...]:
        with self._lock:
            return tuple(
                sorted(self._handlers)
            )
