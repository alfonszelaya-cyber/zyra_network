from __future__ import annotations

from dataclasses import dataclass
from threading import RLock

from .service_adapter import (
    ServiceAdapter,
    ServiceRequest,
    ServiceResponse,
)
from .service_validator import (
    ServiceValidator,
)


@dataclass(frozen=True, slots=True)
class ServiceTarget:
    name: str
    base_url: str
    adapter: ServiceAdapter

    def __post_init__(self) -> None:
        if not self.name.strip():
            raise ValueError(
                "Service target name cannot be empty"
            )

        if not self.base_url.strip():
            raise ValueError(
                "Service target URL cannot be empty"
            )


class ServiceGateway:
    def __init__(
        self,
        validator: ServiceValidator | None = None,
    ) -> None:

        self.validator = (
            validator
            or ServiceValidator()
        )

        self._targets: dict[
            str,
            ServiceTarget,
        ] = {}

        self._lock = RLock()

    def register(
        self,
        target: ServiceTarget,
        *,
        replace: bool = False,
    ) -> None:

        self.validator.require_valid_url(
            target.base_url
        )

        key = target.name.strip().lower()

        with self._lock:
            if (
                key in self._targets
                and not replace
            ):
                raise ValueError(
                    f"Service target already exists: {key}"
                )

            self._targets[key] = target

    def send(
        self,
        service: str,
        request: ServiceRequest,
    ) -> ServiceResponse:

        with self._lock:
            try:
                target = self._targets[
                    service.strip().lower()
                ]
            except KeyError as exc:
                raise LookupError(
                    f"Service target not found: {service}"
                ) from exc

        return target.adapter.send(
            request
        )

    def remove(
        self,
        service: str,
    ) -> bool:

        with self._lock:
            target = self._targets.pop(
                service.strip().lower(),
                None,
            )

        if target is None:
            return False

        target.adapter.close()
        return True

    def list(
        self,
    ) -> tuple[ServiceTarget, ...]:

        with self._lock:
            return tuple(
                self._targets[name]
                for name in sorted(
                    self._targets
                )
            )

    def close(self) -> None:
        with self._lock:
            targets = tuple(
                self._targets.values()
            )
            self._targets.clear()

        for target in targets:
            target.adapter.close()


__all__ = [
    "ServiceTarget",
    "ServiceGateway",
]
