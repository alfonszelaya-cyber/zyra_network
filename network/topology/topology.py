"""
ZYRA Network topology graph.

This layer models nodes and links. It does not make routing,
consensus or failover decisions.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from threading import RLock
from time import time
from typing import Mapping


class NodeType(str, Enum):
    CORE = "core"
    EDGE = "edge"
    SERVICE = "service"
    GATEWAY = "gateway"
    STORAGE = "storage"
    OBSERVER = "observer"


class LinkState(str, Enum):
    UP = "up"
    DEGRADED = "degraded"
    DOWN = "down"
    DRAINING = "draining"


@dataclass(frozen=True, slots=True)
class NetworkNode:
    node_id: str
    node_type: NodeType
    metadata: Mapping[str, str] = field(
        default_factory=dict
    )

    def __post_init__(self) -> None:
        node_id = self.node_id.strip()

        if not node_id:
            raise ValueError(
                "node_id cannot be empty"
            )

        if not isinstance(
            self.node_type,
            NodeType,
        ):
            raise TypeError(
                "node_type must be NodeType"
            )

        object.__setattr__(
            self,
            "node_id",
            node_id,
        )

        object.__setattr__(
            self,
            "metadata",
            dict(self.metadata),
        )


@dataclass(frozen=True, slots=True)
class Link:
    source: str
    destination: str
    state: LinkState = LinkState.UP
    latency_ms: float | None = None
    capacity_bps: int | None = None
    metadata: Mapping[str, str] = field(
        default_factory=dict
    )

    def __post_init__(self) -> None:
        source = self.source.strip()
        destination = self.destination.strip()

        if not source:
            raise ValueError(
                "link source cannot be empty"
            )

        if not destination:
            raise ValueError(
                "link destination cannot be empty"
            )

        if source == destination:
            raise ValueError(
                "self-referential links are not allowed"
            )

        if not isinstance(
            self.state,
            LinkState,
        ):
            raise TypeError(
                "state must be LinkState"
            )

        if (
            self.latency_ms is not None
            and self.latency_ms < 0
        ):
            raise ValueError(
                "latency_ms cannot be negative"
            )

        if (
            self.capacity_bps is not None
            and self.capacity_bps <= 0
        ):
            raise ValueError(
                "capacity_bps must be positive"
            )

        object.__setattr__(
            self,
            "source",
            source,
        )

        object.__setattr__(
            self,
            "destination",
            destination,
        )

        object.__setattr__(
            self,
            "metadata",
            dict(self.metadata),
        )


@dataclass(frozen=True, slots=True)
class TopologySnapshot:
    version: int
    created_at: float
    nodes: tuple[NetworkNode, ...]
    links: tuple[Link, ...]


class NetworkGraph:
    """Thread-safe authoritative local topology graph."""

    def __init__(self) -> None:
        self._nodes: dict[
            str,
            NetworkNode,
        ] = {}

        self._links: dict[
            tuple[str, str],
            Link,
        ] = {}

        self._version = 0
        self._lock = RLock()

    @property
    def version(self) -> int:
        with self._lock:
            return self._version

    def add_node(
        self,
        node: NetworkNode,
    ) -> None:
        if not isinstance(
            node,
            NetworkNode,
        ):
            raise TypeError(
                "node must be NetworkNode"
            )

        with self._lock:
            if node.node_id in self._nodes:
                raise ValueError(
                    f"network node already exists: "
                    f"{node.node_id}"
                )

            self._nodes[
                node.node_id
            ] = node

            self._version += 1

    def remove_node(
        self,
        node_id: str,
    ) -> bool:
        node_id = node_id.strip()

        with self._lock:
            if (
                self._nodes.pop(
                    node_id,
                    None,
                )
                is None
            ):
                return False

            keys = tuple(
                key
                for key in self._links
                if node_id in key
            )

            for key in keys:
                del self._links[key]

            self._version += 1
            return True

    def get_node(
        self,
        node_id: str,
    ) -> NetworkNode | None:
        with self._lock:
            return self._nodes.get(
                node_id.strip()
            )

    def add_link(
        self,
        link: Link,
    ) -> None:
        if not isinstance(
            link,
            Link,
        ):
            raise TypeError(
                "link must be Link"
            )

        key = (
            link.source,
            link.destination,
        )

        with self._lock:
            if link.source not in self._nodes:
                raise LookupError(
                    f"source node does not exist: "
                    f"{link.source}"
                )

            if (
                link.destination
                not in self._nodes
            ):
                raise LookupError(
                    f"destination node does not exist: "
                    f"{link.destination}"
                )

            if key in self._links:
                raise ValueError(
                    f"link already exists: {key}"
                )

            self._links[key] = link
            self._version += 1

    def remove_link(
        self,
        source: str,
        destination: str,
    ) -> bool:
        key = (
            source.strip(),
            destination.strip(),
        )

        with self._lock:
            if (
                self._links.pop(
                    key,
                    None,
                )
                is None
            ):
                return False

            self._version += 1
            return True

    def neighbors(
        self,
        node_id: str,
    ) -> tuple[NetworkNode, ...]:
        node_id = node_id.strip()

        with self._lock:
            if node_id not in self._nodes:
                raise LookupError(
                    f"node not found: {node_id}"
                )

            neighbor_ids = {
                link.destination
                for link in self._links.values()
                if (
                    link.source == node_id
                    and link.state
                    in {
                        LinkState.UP,
                        LinkState.DEGRADED,
                    }
                )
            }

            return tuple(
                self._nodes[
                    neighbor_id
                ]
                for neighbor_id
                in sorted(
                    neighbor_ids
                )
            )

    def set_link_state(
        self,
        source: str,
        destination: str,
        state: LinkState,
    ) -> None:
        if not isinstance(
            state,
            LinkState,
        ):
            raise TypeError(
                "state must be LinkState"
            )

        key = (
            source.strip(),
            destination.strip(),
        )

        with self._lock:
            link = self._links.get(key)

            if link is None:
                raise LookupError(
                    f"link not found: {key}"
                )

            self._links[key] = Link(
                source=link.source,
                destination=link.destination,
                state=state,
                latency_ms=link.latency_ms,
                capacity_bps=link.capacity_bps,
                metadata=link.metadata,
            )

            self._version += 1

    def snapshot(
        self,
    ) -> TopologySnapshot:
        with self._lock:
            return TopologySnapshot(
                version=self._version,
                created_at=time(),
                nodes=tuple(
                    self._nodes.values()
                ),
                links=tuple(
                    self._links.values()
                ),
            )


__all__ = [
    "NodeType",
    "LinkState",
    "NetworkNode",
    "Link",
    "TopologySnapshot",
    "NetworkGraph",
]
