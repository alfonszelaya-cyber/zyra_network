"""
Production load-balancing primitives.

Supports deterministic policies without coupling Network to a
specific proxy or cloud provider.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from threading import RLock


class BackendState(str, Enum):
    ACTIVE = "active"
    DRAINING = "draining"
    UNHEALTHY = "unhealthy"
    DISABLED = "disabled"


class LoadBalancingPolicy(str, Enum):
    ROUND_ROBIN = "round_robin"
    LEAST_CONNECTIONS = "least_connections"
    WEIGHTED = "weighted"


@dataclass(slots=True)
class Backend:
    backend_id: str
    endpoint: str
    weight: int = 1
    state: BackendState = BackendState.ACTIVE
    connections: int = 0
    metadata: dict[str, str] = field(
        default_factory=dict
    )

    def __post_init__(self) -> None:
        self.backend_id = self.backend_id.strip()
        self.endpoint = self.endpoint.strip()

        if not self.backend_id:
            raise ValueError(
                "backend_id cannot be empty"
            )

        if not self.endpoint:
            raise ValueError(
                "backend endpoint cannot be empty"
            )

        if self.weight <= 0:
            raise ValueError(
                "backend weight must be positive"
            )

        if self.connections < 0:
            raise ValueError(
                "connections cannot be negative"
            )


class LoadBalancer:
    """Thread-safe backend selector."""

    def __init__(
        self,
        policy: LoadBalancingPolicy = (
            LoadBalancingPolicy.ROUND_ROBIN
        ),
    ) -> None:

        if not isinstance(
            policy,
            LoadBalancingPolicy,
        ):
            raise TypeError(
                "policy must be LoadBalancingPolicy"
            )

        self._policy = policy

        self._backends: dict[
            str,
            Backend,
        ] = {}

        self._cursor = 0
        self._lock = RLock()

    @property
    def policy(
        self,
    ) -> LoadBalancingPolicy:
        return self._policy

    def register(
        self,
        backend: Backend,
    ) -> None:

        if not isinstance(
            backend,
            Backend,
        ):
            raise TypeError(
                "backend must be Backend"
            )

        with self._lock:
            if (
                backend.backend_id
                in self._backends
            ):
                raise ValueError(
                    "backend already exists: "
                    f"{backend.backend_id}"
                )

            self._backends[
                backend.backend_id
            ] = backend

    def unregister(
        self,
        backend_id: str,
    ) -> bool:

        with self._lock:
            return (
                self._backends.pop(
                    backend_id.strip(),
                    None,
                )
                is not None
            )

    def set_state(
        self,
        backend_id: str,
        state: BackendState,
    ) -> Backend:

        if not isinstance(
            state,
            BackendState,
        ):
            raise TypeError(
                "state must be BackendState"
            )

        with self._lock:
            backend = self._backends.get(
                backend_id.strip()
            )

            if backend is None:
                raise LookupError(
                    f"backend not found: "
                    f"{backend_id}"
                )

            backend.state = state

            return backend

    def connection_open(
        self,
        backend_id: str,
    ) -> None:

        with self._lock:
            backend = self._backends.get(
                backend_id.strip()
            )

            if backend is None:
                raise LookupError(
                    f"backend not found: "
                    f"{backend_id}"
                )

            backend.connections += 1

    def connection_close(
        self,
        backend_id: str,
    ) -> None:

        with self._lock:
            backend = self._backends.get(
                backend_id.strip()
            )

            if backend is None:
                raise LookupError(
                    f"backend not found: "
                    f"{backend_id}"
                )

            if backend.connections == 0:
                raise ValueError(
                    "backend connection count "
                    "cannot become negative"
                )

            backend.connections -= 1

    def select(
        self,
    ) -> Backend:

        with self._lock:
            candidates = tuple(
                backend
                for backend
                in self._backends.values()
                if backend.state
                is BackendState.ACTIVE
            )

            if not candidates:
                raise LookupError(
                    "no active backends available"
                )

            ordered = tuple(
                sorted(
                    candidates,
                    key=lambda item: (
                        item.backend_id
                    ),
                )
            )

            if self._policy is (
                LoadBalancingPolicy.LEAST_CONNECTIONS
            ):
                return min(
                    ordered,
                    key=lambda item: (
                        item.connections,
                        item.backend_id,
                    ),
                )

            if self._policy is (
                LoadBalancingPolicy.WEIGHTED
            ):
                selected = max(
                    ordered,
                    key=lambda item: (
                        item.weight,
                        -item.connections,
                        item.backend_id,
                    ),
                )

                return selected

            selected = ordered[
                self._cursor
                % len(ordered)
            ]

            self._cursor += 1

            return selected

    def snapshot(
        self,
    ) -> tuple[Backend, ...]:

        with self._lock:
            return tuple(
                Backend(
                    backend_id=item.backend_id,
                    endpoint=item.endpoint,
                    weight=item.weight,
                    state=item.state,
                    connections=item.connections,
                    metadata=dict(
                        item.metadata
                    ),
                )
                for item
                in self._backends.values()
            )


__all__ = [
    "BackendState",
    "LoadBalancingPolicy",
    "Backend",
    "LoadBalancer",
]
