"""
Production replication coordination primitives.

This layer tracks replication peers and sequence progress.
Durable data storage remains owned by Storage.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from threading import RLock
from time import monotonic


class ReplicationState(str, Enum):
    CATCHING_UP = "catching_up"
    SYNCED = "synced"
    DEGRADED = "degraded"
    OFFLINE = "offline"


@dataclass(frozen=True, slots=True)
class ReplicationStatus:
    local_sequence: int
    peer_sequence: int
    lag: int
    state: ReplicationState


@dataclass(slots=True)
class ReplicationPeer:
    peer_id: str
    endpoint: str
    sequence: int = 0
    state: ReplicationState = (
        ReplicationState.CATCHING_UP
    )
    metadata: dict[str, str] = field(
        default_factory=dict
    )
    updated_at: float = field(
        default_factory=monotonic
    )

    def __post_init__(self) -> None:
        self.peer_id = self.peer_id.strip()
        self.endpoint = self.endpoint.strip()

        if not self.peer_id:
            raise ValueError(
                "peer_id cannot be empty"
            )

        if not self.endpoint:
            raise ValueError(
                "peer endpoint cannot be empty"
            )

        if self.sequence < 0:
            raise ValueError(
                "sequence cannot be negative"
            )


class ReplicationManager:
    """Thread-safe replication progress manager."""

    def __init__(self) -> None:
        self._local_sequence = 0

        self._peers: dict[
            str,
            ReplicationPeer,
        ] = {}

        self._lock = RLock()

    @property
    def local_sequence(self) -> int:
        with self._lock:
            return self._local_sequence

    def advance_local(
        self,
        sequence: int | None = None,
    ) -> int:

        with self._lock:
            if sequence is None:
                self._local_sequence += 1
            else:
                if sequence < (
                    self._local_sequence
                ):
                    raise ValueError(
                        "local sequence cannot move backwards"
                    )

                self._local_sequence = sequence

            self._refresh_states()

            return self._local_sequence

    def register_peer(
        self,
        peer: ReplicationPeer,
    ) -> None:

        if not isinstance(
            peer,
            ReplicationPeer,
        ):
            raise TypeError(
                "peer must be ReplicationPeer"
            )

        with self._lock:
            if peer.peer_id in self._peers:
                raise ValueError(
                    "replication peer already exists: "
                    f"{peer.peer_id}"
                )

            self._peers[
                peer.peer_id
            ] = peer

            self._refresh_states()

    def update_peer(
        self,
        peer_id: str,
        sequence: int,
    ) -> ReplicationStatus:

        peer_id = peer_id.strip()

        if sequence < 0:
            raise ValueError(
                "sequence cannot be negative"
            )

        with self._lock:
            peer = self._peers.get(
                peer_id
            )

            if peer is None:
                raise LookupError(
                    f"replication peer not found: "
                    f"{peer_id}"
                )

            if sequence < peer.sequence:
                raise ValueError(
                    "peer sequence cannot move backwards"
                )

            peer.sequence = sequence
            peer.updated_at = monotonic()

            self._refresh_states()

            return self.status(
                peer_id
            )

    def status(
        self,
        peer_id: str,
    ) -> ReplicationStatus:

        with self._lock:
            peer = self._peers.get(
                peer_id.strip()
            )

            if peer is None:
                raise LookupError(
                    f"replication peer not found: "
                    f"{peer_id}"
                )

            lag = max(
                0,
                self._local_sequence
                - peer.sequence,
            )

            return ReplicationStatus(
                local_sequence=(
                    self._local_sequence
                ),
                peer_sequence=(
                    peer.sequence
                ),
                lag=lag,
                state=peer.state,
            )

    def _refresh_states(
        self,
    ) -> None:

        for peer in self._peers.values():
            if peer.state is (
                ReplicationState.OFFLINE
            ):
                continue

            lag = (
                self._local_sequence
                - peer.sequence
            )

            if lag <= 0:
                peer.state = (
                    ReplicationState.SYNCED
                )

            elif lag <= 100:
                peer.state = (
                    ReplicationState.CATCHING_UP
                )

            else:
                peer.state = (
                    ReplicationState.DEGRADED
                )

    def peers(
        self,
    ) -> tuple[ReplicationPeer, ...]:

        with self._lock:
            return tuple(
                ReplicationPeer(
                    peer_id=peer.peer_id,
                    endpoint=peer.endpoint,
                    sequence=peer.sequence,
                    state=peer.state,
                    metadata=dict(
                        peer.metadata
                    ),
                    updated_at=peer.updated_at,
                )
                for peer
                in self._peers.values()
            )


__all__ = [
    "ReplicationState",
    "ReplicationStatus",
    "ReplicationPeer",
    "ReplicationManager",
]
