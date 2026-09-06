"""Weighted round-robin backend selection."""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from threading import RLock


class BackendStatus(str, Enum):
    ACTIVE = "active"
    DRAINING = "draining"
    OFFLINE = "offline"


@dataclass(slots=True)
class Backend:
    backend_id: str
    endpoint: str
    weight: int = 1
    status: BackendStatus = (
        BackendStatus.ACTIVE
    )
    failures: int = 0


class LoadBalancer:
    """Thread-safe weighted backend selector."""

    def __init__(self) -> None:
        self._backends: dict[
            str,
            Backend,
        ] = {}

        self._cursor = 0
        self._lock = RLock()

    def register(
        self,
        backend_id: str,
        endpoint: str,
        *,
        weight: int = 1,
    ) -> Backend:
        if not backend_id.strip():
            raise ValueError(
                "backend_id is required"
            )

        if not endpoint.strip():
            raise ValueError(
                "endpoint is required"
            )

        if weight <= 0:
            raise ValueError(
                "weight must be greater than zero"
            )

        backend = Backend(
            backend_id=backend_id,
            endpoint=endpoint,
            weight=weight,
        )

        with self._lock:
            self._backends[
                backend_id
            ] = backend

        return backend

    def set_status(
        self,
        backend_id: str,
        status: BackendStatus,
    ) -> None:
        with self._lock:
            self._backends[
                backend_id
            ].status = status

    def record_failure(
        self,
        backend_id: str,
    ) -> None:
        with self._lock:
            self._backends[
                backend_id
            ].failures += 1

    def choose(self) -> Backend:
        with self._lock:
            active: list[
                Backend
            ] = []

            for backend in (
                self._backends.values()
            ):
                if (
                    backend.status
                    is BackendStatus.ACTIVE
                ):
                    active.extend(
                        [backend]
                        * backend.weight
                    )

            if not active:
                raise RuntimeError(
                    "no active backend available"
                )

            backend = active[
                self._cursor
                % len(active)
            ]

            self._cursor += 1

            return backend

    def snapshot(
        self,
    ) -> tuple[Backend, ...]:
        with self._lock:
            return tuple(
                self._backends.values()
            )


__all__ = [
    "Backend",
    "BackendStatus",
    "LoadBalancer",
]
