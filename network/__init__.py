"""
ZYRA Network.

Foundational network layer for the distributed ZYRA platform.

Block 01 provides:
    - transport primitives
    - network topology
    - service discovery
    - heartbeat/liveness
    - cluster membership

Higher-level routing, failover, quorum, replication,
load-balancing, firewall, sessions and diagnostics are
implemented in subsequent Network blocks.
"""

from .transport import (
    ConnectionState,
    Frame,
    FrameType,
    NetworkTransport,
    TransportAddress,
    TransportError,
    TransportManager,
)

from .topology import (
    Link,
    LinkState,
    NetworkGraph,
    NetworkNode,
    NodeType,
    TopologySnapshot,
)

from .discovery import (
    DiscoveryRecord,
    DiscoveryRegistry,
    DiscoveryStatus,
)

from .heartbeat import (
    Heartbeat,
    HeartbeatMonitor,
    HeartbeatState,
)

from .cluster import (
    Cluster,
    ClusterMember,
    ClusterMemberState,
    ClusterSnapshot,
)

__all__ = [
    "ConnectionState",
    "Frame",
    "FrameType",
    "NetworkTransport",
    "TransportAddress",
    "TransportError",
    "TransportManager",
    "Link",
    "LinkState",
    "NetworkGraph",
    "NetworkNode",
    "NodeType",
    "TopologySnapshot",
    "DiscoveryRecord",
    "DiscoveryRegistry",
    "DiscoveryStatus",
    "Heartbeat",
    "HeartbeatMonitor",
    "HeartbeatState",
    "Cluster",
    "ClusterMember",
    "ClusterMemberState",
    "ClusterSnapshot",
]
