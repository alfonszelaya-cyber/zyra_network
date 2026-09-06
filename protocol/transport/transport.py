from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from threading import RLock
from typing import Protocol


class TransportState(str, Enum):
    DISCONNECTED = "disconnected"
    CONNECTED = "connected"
    CLOSED = "closed"


@dataclass(frozen=True, slots=True)
class TransportAddress:
    host: str
    port: int
    scheme: str = "tcp"

    def __post_init__(self) -> None:
        host = self.host.strip()
        scheme = self.scheme.strip().lower()

        if not host:
            raise ValueError(
                "Transport host cannot be empty"
            )

        if not 1 <= self.port <= 65535:
            raise ValueError(
                "Transport port must be between "
                "1 and 65535"
            )

        if not scheme:
            raise ValueError(
                "Transport scheme cannot be empty"
            )

        object.__setattr__(
            self,
            "host",
            host,
        )

        object.__setattr__(
            self,
            "scheme",
            scheme,
        )

    def as_uri(self) -> str:
        return (
            f"{self.scheme}://"
            f"{self.host}:{self.port}"
        )


class TransportChannel(Protocol):

    def connect(
        self,
        address: TransportAddress,
    ) -> None:
        ...

    def send(
        self,
        payload: bytes,
    ) -> None:
        ...

    def close(self) -> None:
        ...


class InMemoryTransport:

    def __init__(self) -> None:
        self._state = (
            TransportState.DISCONNECTED
        )

        self._address: (
            TransportAddress | None
        ) = None

        self._frames: list[bytes] = []
        self._lock = RLock()

    @property
    def state(self) -> TransportState:
        with self._lock:
            return self._state

    @property
    def address(
        self,
    ) -> TransportAddress | None:

        with self._lock:
            return self._address

    def connect(
        self,
        address: TransportAddress,
    ) -> None:

        with self._lock:
            if self._state is TransportState.CLOSED:
                raise RuntimeError(
                    "Transport is permanently closed"
                )

            self._address = address
            self._state = (
                TransportState.CONNECTED
            )

    def send(
        self,
        payload: bytes,
    ) -> None:

        if not isinstance(payload, bytes):
            raise TypeError(
                "Transport payload must be bytes"
            )

        with self._lock:
            if (
                self._state
                is not TransportState.CONNECTED
            ):
                raise RuntimeError(
                    "Transport is not connected"
                )

            self._frames.append(
                bytes(payload)
            )

    def receive_all(
        self,
    ) -> tuple[bytes, ...]:

        with self._lock:
            frames = tuple(self._frames)
            self._frames.clear()
            return frames

    def close(self) -> None:
        with self._lock:
            self._state = (
                TransportState.CLOSED
            )
            self._address = None


class TransportManager:

    def __init__(self) -> None:
        self._channels: dict[
            str,
            TransportChannel,
        ] = {}

        self._lock = RLock()

    def register(
        self,
        name: str,
        channel: TransportChannel,
    ) -> None:

        name = name.strip()

        if not name:
            raise ValueError(
                "Transport channel name "
                "cannot be empty"
            )

        for method in (
            "connect",
            "send",
            "close",
        ):
            if not callable(
                getattr(channel, method, None)
            ):
                raise TypeError(
                    f"Transport channel missing "
                    f"{method}()"
                )

        with self._lock:
            if name in self._channels:
                raise ValueError(
                    f"Transport already registered: "
                    f"{name}"
                )

            self._channels[name] = channel

    def get(
        self,
        name: str,
    ) -> TransportChannel:

        normalized = name.strip()

        with self._lock:
            try:
                return self._channels[
                    normalized
                ]
            except KeyError as exc:
                raise LookupError(
                    f"Transport not found: "
                    f"{normalized}"
                ) from exc

    def unregister(
        self,
        name: str,
    ) -> bool:

        with self._lock:
            return (
                self._channels.pop(
                    name.strip(),
                    None,
                )
                is not None
            )

    def names(
        self,
    ) -> tuple[str, ...]:

        with self._lock:
            return tuple(
                sorted(
                    self._channels
                )
            )


__all__ = [
    "TransportState",
    "TransportAddress",
    "TransportChannel",
    "InMemoryTransport",
    "TransportManager",
]
