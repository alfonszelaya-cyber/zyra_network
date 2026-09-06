from __future__ import annotations

from dataclasses import dataclass
from threading import RLock
from typing import Any


@dataclass(frozen=True, slots=True)
class KernelStatus:
    initialized: bool
    running: bool


class FoundationKernel:
    """Minimal deterministic kernel boundary for foundation services."""

    def __init__(self) -> None:
        self._initialized = False
        self._running = False
        self._services: dict[str, Any] = {}
        self._lock = RLock()

    def initialize(self) -> None:
        with self._lock:
            if self._initialized:
                return
            self._initialized = True

    def start(self) -> None:
        with self._lock:
            if not self._initialized:
                raise RuntimeError(
                    "Kernel must be initialized before start"
                )
            self._running = True

    def stop(self) -> None:
        with self._lock:
            self._running = False

    def register_service(self, name: str, service: Any) -> None:
        normalized = name.strip()

        if not normalized:
            raise ValueError("Service name cannot be empty")

        if service is None:
            raise ValueError("Service cannot be None")

        with self._lock:
            if normalized in self._services:
                raise ValueError(
                    f"Service already registered: {normalized}"
                )
            self._services[normalized] = service

    def get_service(self, name: str) -> Any:
        with self._lock:
            return self._services[name.strip()]

    def status(self) -> KernelStatus:
        with self._lock:
            return KernelStatus(
                initialized=self._initialized,
                running=self._running,
            )


__all__ = ["FoundationKernel", "KernelStatus"]
