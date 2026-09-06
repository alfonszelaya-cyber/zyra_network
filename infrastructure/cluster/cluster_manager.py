"""
Thread-safe cluster membership and heartbeat registry.

This module owns local cluster state. Distributed consensus,
service discovery transports and cloud orchestration remain
separate adapters.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from threading import RLock
from time import monotonic
from typing import Mapping


class MemberStatus(str, Enum):
    JOINING = "joining"
    READY = "ready"
    DEGRADED = "degraded"
    LEAVING = "leaving"
    OFFLINE = "offline"


@dataclass(slots=True)
class ClusterMember:
    node_id: str
    endpoint: str
    status: MemberStatus = MemberStatus.JOINING
    metadata: dict[str, str] = field(default_factory=dict)
    last_heartbeat: float = field(
        default_factory=monotonic
    )
    generation: int = 0


@dataclass(frozen=True, slots=True)
class ClusterState:
    cluster_id: str
    generation: int
    members: tuple[ClusterMember, ...]


class ClusterManager:
    """Thread-safe cluster membership manager."""

    def __init__(
        self,
        cluster_id: str,
    ) -> None:
        if not cluster_id.strip():
            raise ValueError(
                "cluster_id is required"
            )

        self._cluster_id = cluster_id
        self._generation = 0
        self._members: dict[
            str,
            ClusterMember,
        ] = {}
        self._lock = RLock()

    def register(
        self,
        node_id: str,
        endpoint: str,
        metadata: Mapping[str, str] | None = None,
    ) -> ClusterMember:
        if not node_id.strip():
            raise ValueError(
                "node_id is required"
            )

        if not endpoint.strip():
            raise ValueError(
                "endpoint is required"
            )

        with self._lock:
            self._generation += 1

            member = ClusterMember(
                node_id=node_id,
                endpoint=endpoint,
                status=MemberStatus.READY,
                metadata=dict(
                    metadata or {}
                ),
                last_heartbeat=monotonic(),
                generation=self._generation,
            )

            self._members[node_id] = member

            return member

    def heartbeat(
        self,
        node_id: str,
    ) -> None:
        with self._lock:
            member = self._members.get(
                node_id
            )

            if member is None:
                raise KeyError(
                    f"unknown cluster member: {node_id}"
                )

            member.last_heartbeat = monotonic()
            member.status = MemberStatus.READY

    def set_status(
        self,
        node_id: str,
        status: MemberStatus,
    ) -> None:
        if not isinstance(
            status,
            MemberStatus,
        ):
            raise TypeError(
                "status must be MemberStatus"
            )

        with self._lock:
            member = self._members.get(
                node_id
            )

            if member is None:
                raise KeyError(
                    f"unknown cluster member: {node_id}"
                )

            self._generation += 1
            member.status = status
            member.generation = self._generation

    def remove(
        self,
        node_id: str,
    ) -> None:
        with self._lock:
            if (
                self._members.pop(
                    node_id,
                    None,
                )
                is not None
            ):
                self._generation += 1

    def snapshot(
        self,
    ) -> ClusterState:
        with self._lock:
            members = tuple(
                ClusterMember(
                    node_id=member.node_id,
                    endpoint=member.endpoint,
                    status=member.status,
                    metadata=dict(
                        member.metadata
                    ),
                    last_heartbeat=(
                        member.last_heartbeat
                    ),
                    generation=member.generation,
                )
                for member
                in self._members.values()
            )

            return ClusterState(
                cluster_id=self._cluster_id,
                generation=self._generation,
                members=members,
            )


__all__ = [
    "ClusterManager",
    "ClusterMember",
    "ClusterState",
    "MemberStatus",
]
