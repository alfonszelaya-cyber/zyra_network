"""
Production transport abstractions for ZYRA Network.

The Network layer defines the stable transport contract.
Concrete TCP, TLS, QUIC, Unix-socket or cloud transports may
implement the contract without changing callers.

Responsibilities:
    - endpoint representation
    - frame representation
    - transport lifecycle
    - transport registration
    - deterministic local transport for validation

Responsibilities deliberately excluded:
    - protocol serialization
    - authentication
    - authorization
    - routing decisions
    - consensus
    - persistence
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from threading import RLock
from typing import Mapping, Protocol


MAX_FRAME_SIZE = 16 * 1024 * 1024
MAX_HEADER_COUNT = 128


class TransportError(RuntimeError):
    """Base exception for transport failures."""


class ConnectionState(str, Enum):
    DISCONNECTED = "disconnected"
    CONNECTING = "connecting"
    CONNECTED = "connected"
    DRAINING = "draining"
    CLOSED = "closed"
    FAILED = "failed"


class FrameType(str, Enum):
    DATA = "data"
    CONTROL = "control"
    HEARTBEAT = "heartbeat"
    ACK = "ack"
    ERROR = "error"


@dataclass(frozen=True, slots=True)
class TransportAddress:
    """Immutable transport endpoint."""

    host: str
    port: int
    scheme: str = "tcp"
    secure: bool = False

    def __post_init__(self) -> None:
        host = self.host.strip()
        scheme = self.scheme.strip().lower()

        if not host:
            raise ValueError(
                "transport host cannot be empty"
            )

        if not 1 <= self.port <= 65535:
            raise ValueError(
                "transport port must be between 1 and 65535"
            )

        if not scheme:
            raise ValueError(
                "transport scheme cannot be empty"
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


@dataclass(frozen=True, slots=True)
class Frame:
    """
    Immutable transport frame.

    Payload remains opaque to Network. Serialization belongs
    to the Protocol layer.
    """

    frame_type: FrameType
    payload: bytes
    sequence: int
    headers: Mapping[str, str] = field(
        default_factory=dict
    )

    def __post_init__(self) -> None:
        if not isinstance(
            self.frame_type,
            FrameType,
        ):
            raise TypeError(
                "frame_type must be FrameType"
            )

        if not isinstance(
            self.payload,
            bytes,
        ):
            raise TypeError(
                "frame payload must be bytes"
            )

        if self.sequence < 0:
            raise ValueError(
                "frame sequence cannot be negative"
            )

        if len(self.payload) > MAX_FRAME_SIZE:
            raise ValueError(
                "frame payload exceeds maximum size"
            )

        normalized = {
            str(key): str(value)
            for key, value in self.headers.items()
        }

        if len(normalized) > MAX_HEADER_COUNT:
            raise ValueError(
                "frame header count exceeds maximum"
            )

        object.__setattr__(
            self,
            "payload",
            bytes(self.payload),
        )

        object.__setattr__(
            self,
            "headers",
            normalized,
        )

    @property
    def size(self) -> int:
        return len(self.payload)


class NetworkTransport(Protocol):
    """
    Stable contract for every concrete transport.
    """

    @property
    def state(self) -> ConnectionState:
        ...

    @property
    def address(
        self,
    ) -> TransportAddress | None:
        ...

    def connect(
        self,
        address: TransportAddress,
    ) -> None:
        ...

    def send(
        self,
        frame: Frame,
    ) -> None:
        ...

    def receive(
        self,
    ) -> tuple[Frame, ...]:
        ...

    def close(self) -> None:
        ...


class TransportManager:
    """
    Thread-safe transport registry.

    Owns registration and lifecycle coordination but does not
    dictate how individual transports implement I/O.
    """

    def __init__(self) -> None:
        self._transports: dict[
            str,
            NetworkTransport,
        ] = {}

        self._lock = RLock()

    def register(
        self,
        name: str,
        transport: NetworkTransport,
    ) -> None:
        name = name.strip()

        if not name:
            raise ValueError(
                "transport name cannot be empty"
            )

        required = (
            "connect",
            "send",
            "receive",
            "close",
        )

        for method in required:
            if not callable(
                getattr(
                    transport,
                    method,
                    None,
                )
            ):
                raise TypeError(
                    f"transport is missing {method}()"
                )

        with self._lock:
            if name in self._transports:
                raise ValueError(
                    f"transport already registered: {name}"
                )

            self._transports[name] = transport

    def get(
        self,
        name: str,
    ) -> NetworkTransport:
        normalized = name.strip()

        with self._lock:
            try:
                return self._transports[
                    normalized
                ]
            except KeyError as exc:
                raise LookupError(
                    f"transport not found: {normalized}"
                ) from exc

    def unregister(
        self,
        name: str,
    ) -> bool:
        with self._lock:
            return (
                self._transports.pop(
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
                    self._transports
                )
            )

    def close_all(self) -> None:
        errors: list[Exception] = []

        with self._lock:
            transports = tuple(
                self._transports.values()
            )

        for transport in transports:
            try:
                transport.close()
            except Exception as exc:
                errors.append(exc)

        if errors:
            raise TransportError(
                f"{len(errors)} transport(s) "
                "failed during close_all()"
            )


class InMemoryNetworkTransport:
    """
    Deterministic reference transport.

    Used exclusively as a local contract/integration transport.
    Production deployments use concrete NetworkTransport
    implementations.
    """

    def __init__(self) -> None:
        self._state = (
            ConnectionState.DISCONNECTED
        )

        self._address: (
            TransportAddress | None
        ) = None

        self._frames: list[Frame] = []
        self._sequence = 0
        self._lock = RLock()

    @property
    def state(self) -> ConnectionState:
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
        if not isinstance(
            address,
            TransportAddress,
        ):
            raise TypeError(
                "address must be TransportAddress"
            )

        with self._lock:
            if (
                self._state
                is ConnectionState.CLOSED
            ):
                raise TransportError(
                    "closed transport cannot reconnect"
                )

            self._state = (
                ConnectionState.CONNECTING
            )

            self._address = address

            self._state = (
                ConnectionState.CONNECTED
            )

    def send(
        self,
        frame: Frame,
    ) -> None:
        if not isinstance(
            frame,
            Frame,
        ):
            raise TypeError(
                "frame must be Frame"
            )

        with self._lock:
            if (
                self._state
                is not ConnectionState.CONNECTED
            ):
                raise TransportError(
                    "transport is not connected"
                )

            self._frames.append(frame)

    def receive(
        self,
    ) -> tuple[Frame, ...]:
        with self._lock:
            frames = tuple(
                self._frames
            )

            self._frames.clear()

            return frames

    def close(self) -> None:
        with self._lock:
            self._state = (
                ConnectionState.CLOSED
            )

            self._address = None

    def next_sequence(self) -> int:
        with self._lock:
            sequence = self._sequence
            self._sequence += 1
            return sequence


__all__ = [
    "MAX_FRAME_SIZE",
    "MAX_HEADER_COUNT",
    "TransportError",
    "ConnectionState",
    "FrameType",
    "TransportAddress",
    "Frame",
    "NetworkTransport",
    "TransportManager",
    "InMemoryNetworkTransport",
]
