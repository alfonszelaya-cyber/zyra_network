"""Transport-neutral network endpoint registry."""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from threading import RLock


class NetworkState(str, Enum):
    DOWN = "down"
    STARTING = "starting"
    READY = "ready"
    DEGRADED = "degraded"
    STOPPING = "stopping"


@dataclass(frozen=True, slots=True)
class NetworkAddress:
    host: str
    port: int
    protocol: str = "tcp"

    def __post_init__(self) -> None:
        if not self.host.strip():
            raise ValueError(
                "host is required"
            )

        if not 1 <= self.port <= 65535:
            raise ValueError(
                "port must be between 1 and 65535"
            )

        if not self.protocol.strip():
            raise ValueError(
                "protocol is required"
            )


class NetworkManager:
    """Thread-safe endpoint lifecycle manager."""

    def __init__(self) -> None:
        self._state = (
            NetworkState.DOWN
        )

        self._addresses: dict[
            str,
            NetworkAddress,
        ] = {}

        self._lock = RLock()

    def start(self) -> None:
        with self._lock:
            if (
                self._state
                is NetworkState.READY
            ):
                return

            self._state = (
                NetworkState.STARTING
            )

            self._state = (
                NetworkState.READY
            )

    def stop(self) -> None:
        with self._lock:
            self._state = (
                NetworkState.STOPPING
            )

            self._state = (
                NetworkState.DOWN
            )

    def register(
        self,
        name: str,
        address: NetworkAddress,
    ) -> None:
        if not name.strip():
            raise ValueError(
                "address name is required"
            )

        if not isinstance(
            address,
            NetworkAddress,
        ):
            raise TypeError(
                "address must be NetworkAddress"
            )

        with self._lock:
            self._addresses[
                name
            ] = address

    def resolve(
        self,
        name: str,
    ) -> NetworkAddress | None:
        with self._lock:
            return self._addresses.get(
                name
            )

    @property
    def state(self) -> NetworkState:
        with self._lock:
            return self._state


__all__ = [
    "NetworkAddress",
    "NetworkManager",
    "NetworkState",
]
