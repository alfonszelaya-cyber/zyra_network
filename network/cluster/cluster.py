"""
ZYRA Network cluster membership foundation.

Consensus and quorum are intentionally not implemented here.
This module owns membership identity and lifecycle state.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from threading import RLock
from time import monotonic
from typing import Mapping


class ClusterMemberState(str, Enum):
    JOINING = "joining"
    ACTIVE = "active"
    DEGRADED = "degraded"
    LEAVING = "leaving"
    OFFLINE = "offline"


@dataclass(slots=True)
class ClusterMember:
    node_id: str
    endpoint: str
    state: ClusterMemberState = (
        ClusterMemberState.JOINING
    )
    metadata: dict[str, str] = field(
        default_factory=dict
    )
    generation: int = 0
    last_seen: float = field(
        default_factory=monotonic
    )

    def __post_init__(self) -> None:
        self.node_id = self.node_id.strip()
        self.endpoint = self.endpoint.strip()

        if not self.node_id:
            raise ValueError(
                "cluster node_id cannot be empty"
            )

        if not self.endpoint:
            raise ValueError(
                "cluster endpoint cannot be empty"
            )


@dataclass(frozen=True, slots=True)
class ClusterSnapshot:
    cluster_id: str
    generation: int
    members: tuple[ClusterMember, ...]


class Cluster:
    """
    Thread-safe cluster membership authority.
    """

    def __init__(
        self,
        cluster_id: str,
    ) -> None:

        cluster_id = cluster_id.strip()

        if not cluster_id:
            raise ValueError(
                "cluster_id cannot be empty"
            )

        self.cluster_id = cluster_id
        self._generation = 0

        self._members: dict[
            str,
            ClusterMember,
        ] = {}

        self._lock = RLock()

    @property
    def generation(self) -> int:
        with self._lock:
            return self._generation

    def join(
        self,
        node_id: str,
        endpoint: str,
        metadata: Mapping[str, str] | None = None,
    ) -> ClusterMember:

        node_id = node_id.strip()
        endpoint = endpoint.strip()

        if not node_id:
            raise ValueError(
                "node_id cannot be empty"
            )

        if not endpoint:
            raise ValueError(
                "endpoint cannot be empty"
            )

        with self._lock:
            if node_id in self._members:
                raise ValueError(
                    f"cluster member already exists: "
                    f"{node_id}"
                )

            self._generation += 1

            member = ClusterMember(
                node_id=node_id,
                endpoint=endpoint,
                state=ClusterMemberState.ACTIVE,
                metadata=dict(
                    metadata or {}
                ),
                generation=self._generation,
                last_seen=monotonic(),
            )

            self._members[
                node_id
            ] = member

            return member

    def heartbeat(
        self,
        node_id: str,
    ) -> ClusterMember:

        with self._lock:
            member = self._members.get(
                node_id.strip()
            )

            if member is None:
                raise LookupError(
                    f"cluster member not found: "
                    f"{node_id}"
                )

            member.last_seen = monotonic()

            if member.state in {
                ClusterMemberState.DEGRADED,
                ClusterMemberState.OFFLINE,
            }:
                self._generation += 1
                member.generation = (
                    self._generation
                )
                member.state = (
                    ClusterMemberState.ACTIVE
                )

            return member

    def set_state(
        self,
        node_id: str,
        state: ClusterMemberState,
    ) -> ClusterMember:

        if not isinstance(
            state,
            ClusterMemberState,
        ):
            raise TypeError(
                "state must be ClusterMemberState"
            )

        with self._lock:
            member = self._members.get(
                node_id.strip()
            )

            if member is None:
                raise LookupError(
                    f"cluster member not found: "
                    f"{node_id}"
                )

            if member.state is state:
                return member

            self._generation += 1
            member.state = state
            member.generation = (
                self._generation
            )

            return member

    def leave(
        self,
        node_id: str,
    ) -> ClusterMember:

        return self.set_state(
            node_id,
            ClusterMemberState.LEAVING,
        )

    def remove(
        self,
        node_id: str,
    ) -> bool:

        node_id = node_id.strip()

        with self._lock:
            if (
                self._members.pop(
                    node_id,
                    None,
                )
                is None
            ):
                return False

            self._generation += 1
            return True

    def get(
        self,
        node_id: str,
    ) -> ClusterMember | None:

        with self._lock:
            return self._members.get(
                node_id.strip()
            )

    def active_members(
        self,
    ) -> tuple[ClusterMember, ...]:

        with self._lock:
            return tuple(
                member
                for member
                in self._members.values()
                if member.state
                in {
                    ClusterMemberState.ACTIVE,
                    ClusterMemberState.DEGRADED,
                }
            )

    def snapshot(
        self,
    ) -> ClusterSnapshot:

        with self._lock:
            members = tuple(
                ClusterMember(
                    node_id=member.node_id,
                    endpoint=member.endpoint,
                    state=member.state,
                    metadata=dict(
                        member.metadata
                    ),
                    generation=member.generation,
                    last_seen=member.last_seen,
                )
                for member
                in self._members.values()
            )

            return ClusterSnapshot(
                cluster_id=self.cluster_id,
                generation=self._generation,
                members=members,
            )


__all__ = [
    "ClusterMemberState",
    "ClusterMember",
    "ClusterSnapshot",
    "Cluster",
]
