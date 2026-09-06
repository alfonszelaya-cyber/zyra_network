"""Thread-safe provider-neutral service registry."""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from threading import RLock
from time import monotonic


class ServiceStatus(str, Enum):
    ACTIVE = "active"
    DEGRADED = "degraded"
    DRAINING = "draining"
    OFFLINE = "offline"


@dataclass(slots=True)
class ServiceEndpoint:
    service: str
    endpoint: str
    weight: int = 1
    status: ServiceStatus = (
        ServiceStatus.ACTIVE
    )
    metadata: dict[str, str] = field(
        default_factory=dict
    )
    last_seen: float = field(
        default_factory=monotonic
    )


class ServiceRegistry:
    """Thread-safe service endpoint registry."""

    def __init__(self) -> None:
        self._services: dict[
            str,
            dict[str, ServiceEndpoint],
        ] = {}

        self._lock = RLock()

    def register(
        self,
        service: str,
        endpoint: str,
        *,
        weight: int = 1,
        metadata: dict[str, str] | None = None,
    ) -> ServiceEndpoint:
        if not service.strip():
            raise ValueError(
                "service is required"
            )

        if not endpoint.strip():
            raise ValueError(
                "endpoint is required"
            )

        if weight <= 0:
            raise ValueError(
                "weight must be greater than zero"
            )

        item = ServiceEndpoint(
            service=service,
            endpoint=endpoint,
            weight=weight,
            status=ServiceStatus.ACTIVE,
            metadata=dict(
                metadata or {}
            ),
            last_seen=monotonic(),
        )

        with self._lock:
            self._services.setdefault(
                service,
                {},
            )[endpoint] = item

        return item

    def heartbeat(
        self,
        service: str,
        endpoint: str,
    ) -> None:
        with self._lock:
            item = self._services.get(
                service,
                {},
            ).get(endpoint)

            if item is None:
                raise KeyError(
                    f"unknown endpoint: "
                    f"{service}/{endpoint}"
                )

            item.last_seen = monotonic()
            item.status = (
                ServiceStatus.ACTIVE
            )

    def set_status(
        self,
        service: str,
        endpoint: str,
        status: ServiceStatus,
    ) -> None:
        with self._lock:
            item = self._services[
                service
            ][endpoint]

            item.status = status

    def resolve(
        self,
        service: str,
    ) -> tuple[
        ServiceEndpoint,
        ...,
    ]:
        with self._lock:
            return tuple(
                item
                for item in self._services.get(
                    service,
                    {},
                ).values()
                if item.status
                in {
                    ServiceStatus.ACTIVE,
                    ServiceStatus.DEGRADED,
                }
            )

    def remove(
        self,
        service: str,
        endpoint: str,
    ) -> None:
        with self._lock:
            endpoints = self._services.get(
                service
            )

            if not endpoints:
                return

            endpoints.pop(
                endpoint,
                None,
            )

            if not endpoints:
                self._services.pop(
                    service,
                    None,
                )


__all__ = [
    "ServiceEndpoint",
    "ServiceRegistry",
    "ServiceStatus",
]
