from __future__ import annotations

from dataclasses import dataclass
from threading import RLock


@dataclass(frozen=True, slots=True)
class ExternalService:
    service_id: str
    name: str
    endpoint: str
    enabled: bool = True

    def __post_init__(self) -> None:
        if not self.service_id.strip():
            raise ValueError(
                "service_id cannot be empty"
            )

        if not self.name.strip():
            raise ValueError(
                "service name cannot be empty"
            )

        if not self.endpoint.strip():
            raise ValueError(
                "service endpoint cannot be empty"
            )


class ServiceRegistry:
    def __init__(self) -> None:
        self._services: dict[
            str,
            ExternalService,
        ] = {}

        self._lock = RLock()

    def register(
        self,
        service: ExternalService,
        *,
        replace: bool = False,
    ) -> None:

        key = service.service_id.strip()

        with self._lock:
            if (
                key in self._services
                and not replace
            ):
                raise ValueError(
                    f"External service already registered: {key}"
                )

            self._services[key] = service

    def get(
        self,
        service_id: str,
    ) -> ExternalService:

        with self._lock:
            try:
                return self._services[
                    service_id.strip()
                ]
            except KeyError as exc:
                raise LookupError(
                    f"External service not found: {service_id}"
                ) from exc

    def remove(
        self,
        service_id: str,
    ) -> bool:

        with self._lock:
            return (
                self._services.pop(
                    service_id.strip(),
                    None,
                )
                is not None
            )

    def list(
        self,
    ) -> tuple[ExternalService, ...]:

        with self._lock:
            return tuple(
                self._services[key]
                for key in sorted(
                    self._services
                )
            )


__all__ = [
    "ExternalService",
    "ServiceRegistry",
]
