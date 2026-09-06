from __future__ import annotations

from dataclasses import dataclass
from threading import RLock


@dataclass(frozen=True, slots=True)
class ServiceEndpoint:
    service: str
    host: str
    port: int
    protocol: str = "tcp"
    weight: int = 100

    def __post_init__(self) -> None:
        if not self.service.strip():
            raise ValueError(
                "Service name cannot be empty"
            )

        if not self.host.strip():
            raise ValueError(
                "Service host cannot be empty"
            )

        if not 1 <= self.port <= 65535:
            raise ValueError(
                "Service port out of range"
            )

        if self.weight <= 0:
            raise ValueError(
                "Service weight must be positive"
            )


class ServiceDiscovery:
    def __init__(self) -> None:
        self._services: dict[
            str,
            list[ServiceEndpoint],
        ] = {}

        self._lock = RLock()

    def register(
        self,
        endpoint: ServiceEndpoint,
    ) -> None:

        key = endpoint.service.strip().lower()

        with self._lock:
            endpoints = self._services.setdefault(
                key,
                [],
            )

            if endpoint not in endpoints:
                endpoints.append(endpoint)

    def unregister(
        self,
        endpoint: ServiceEndpoint,
    ) -> bool:

        key = endpoint.service.strip().lower()

        with self._lock:
            endpoints = self._services.get(key)

            if not endpoints:
                return False

            try:
                endpoints.remove(endpoint)
            except ValueError:
                return False

            if not endpoints:
                self._services.pop(key)

            return True

    def resolve(
        self,
        service: str,
    ) -> tuple[ServiceEndpoint, ...]:

        key = service.strip().lower()

        with self._lock:
            endpoints = self._services.get(key)

            if not endpoints:
                raise LookupError(
                    f"Service not discovered: {service}"
                )

            return tuple(
                sorted(
                    endpoints,
                    key=lambda item: (
                        -item.weight,
                        item.host,
                        item.port,
                    ),
                )
            )


__all__ = [
    "ServiceEndpoint",
    "ServiceDiscovery",
]
