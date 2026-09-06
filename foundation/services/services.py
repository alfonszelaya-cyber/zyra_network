from __future__ import annotations

from dataclasses import dataclass
from threading import RLock
from typing import Any, Protocol


class ServiceError(RuntimeError):
    """Base service error."""


class ServiceAlreadyRegistered(ServiceError):
    """Service name already exists."""


class ServiceNotFound(ServiceError):
    """Service name does not exist."""


class Service(Protocol):
    def start(self) -> None:
        ...

    def stop(self) -> None:
        ...


@dataclass(frozen=True, slots=True)
class ServiceRecord:
    name: str
    service: Service
    started: bool = False


class ServiceContainer:
    """
    Thread-safe dependency/service container.

    Services are explicitly registered and lifecycle-managed.
    Dependency injection remains independent of any framework.
    """

    def __init__(self) -> None:
        self._services: dict[
            str,
            ServiceRecord,
        ] = {}

        self._lock = RLock()

    def register(
        self,
        name: str,
        service: Service,
    ) -> None:
        if not name.strip():
            raise ValueError(
                "Service name cannot be empty"
            )

        if not hasattr(service, "start") or not hasattr(
            service,
            "stop",
        ):
            raise TypeError(
                "Service must implement start() and stop()"
            )

        with self._lock:
            if name in self._services:
                raise ServiceAlreadyRegistered(
                    f"Service already registered: {name}"
                )

            self._services[name] = ServiceRecord(
                name=name,
                service=service,
                started=False,
            )

    def resolve(
        self,
        name: str,
    ) -> Service:
        with self._lock:
            record = self._services.get(name)

            if record is None:
                raise ServiceNotFound(
                    f"Service not found: {name}"
                )

            return record.service

    def start_all(self) -> None:
        with self._lock:
            records = tuple(
                self._services.values()
            )

        started: list[str] = []

        try:
            for record in records:
                record.service.start()
                started.append(record.name)

                with self._lock:
                    self._services[
                        record.name
                    ] = ServiceRecord(
                        name=record.name,
                        service=record.service,
                        started=True,
                    )

        except Exception:
            for name in reversed(started):
                self._safe_stop(name)

            raise

    def stop_all(self) -> None:
        with self._lock:
            records = tuple(
                self._services.values()
            )

        for record in reversed(records):
            if record.started:
                record.service.stop()

                with self._lock:
                    self._services[
                        record.name
                    ] = ServiceRecord(
                        name=record.name,
                        service=record.service,
                        started=False,
                    )

    def unregister(self, name: str) -> bool:
        with self._lock:
            record = self._services.pop(
                name,
                None,
            )

        if record is None:
            return False

        if record.started:
            record.service.stop()

        return True

    def names(self) -> tuple[str, ...]:
        with self._lock:
            return tuple(
                sorted(self._services)
            )

    def status(self) -> dict[str, bool]:
        with self._lock:
            return {
                name: record.started
                for name, record
                in self._services.items()
            }

    def _safe_stop(self, name: str) -> None:
        with self._lock:
            record = self._services.get(name)

        if record is None:
            return

        try:
            record.service.stop()
        finally:
            with self._lock:
                self._services[
                    name
                ] = ServiceRecord(
                    name=name,
                    service=record.service,
                    started=False,
                )
