"""Thread-safe infrastructure node registry."""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from threading import RLock
from time import time


class NodeStatus(str, Enum):
    PROVISIONING = "provisioning"
    READY = "ready"
    DEGRADED = "degraded"
    DRAINING = "draining"
    OFFLINE = "offline"


@dataclass(slots=True)
class Node:
    node_id: str
    hostname: str
    status: NodeStatus = (
        NodeStatus.PROVISIONING
    )
    labels: dict[str, str] = field(
        default_factory=dict
    )
    registered_at: float = field(
        default_factory=time
    )
    last_heartbeat: float = field(
        default_factory=time
    )


class NodeManager:
    """Thread-safe node lifecycle manager."""

    def __init__(self) -> None:
        self._nodes: dict[
            str,
            Node,
        ] = {}

        self._lock = RLock()

    def register(
        self,
        node_id: str,
        hostname: str,
        labels: dict[str, str] | None = None,
    ) -> Node:
        if not node_id.strip():
            raise ValueError(
                "node_id is required"
            )

        if not hostname.strip():
            raise ValueError(
                "hostname is required"
            )

        node = Node(
            node_id=node_id,
            hostname=hostname,
            labels=dict(
                labels or {}
            ),
        )

        with self._lock:
            self._nodes[
                node_id
            ] = node

        return node

    def ready(
        self,
        node_id: str,
    ) -> None:
        with self._lock:
            node = self._nodes[
                node_id
            ]

            node.status = (
                NodeStatus.READY
            )
            node.last_heartbeat = time()

    def heartbeat(
        self,
        node_id: str,
    ) -> None:
        with self._lock:
            self._nodes[
                node_id
            ].last_heartbeat = time()

    def set_status(
        self,
        node_id: str,
        status: NodeStatus,
    ) -> None:
        if not isinstance(
            status,
            NodeStatus,
        ):
            raise TypeError(
                "status must be NodeStatus"
            )

        with self._lock:
            self._nodes[
                node_id
            ].status = status

    def get(
        self,
        node_id: str,
    ) -> Node | None:
        with self._lock:
            return self._nodes.get(
                node_id
            )

    def snapshot(
        self,
    ) -> tuple[Node, ...]:
        with self._lock:
            return tuple(
                self._nodes.values()
            )


__all__ = [
    "Node",
    "NodeManager",
    "NodeStatus",
]
