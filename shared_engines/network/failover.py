"""Quorum-gated failover: no split-brain, ever."""
from __future__ import annotations

from shared_engines.audit.chain import AuditTrail
from shared_engines.common.validation import require_non_empty_str
from shared_engines.network.cluster import (
    ClusterManager,
    NodeRole,
)
from shared_engines.network.errors import NoQuorumError

EVENT_FAILOVER = "network.failover.elected"


class FailoverCoordinator:
    """Elects a new primary under quorum, audited."""

    def __init__(
        self,
        *,
        cluster: ClusterManager,
        audit: AuditTrail,
    ) -> None:
        self._cluster = cluster
        self._audit = audit

    def elect_new_primary(
        self, *, failed_primary: str
    ) -> str:
        require_non_empty_str(failed_primary, "failed_primary")
        registered = self._cluster.all_nodes()
        if len(registered) == 0:
            raise NoQuorumError("cluster is empty")
        active = self._cluster.active_nodes()
        majority = len(registered) // 2 + 1
        if len(active) < majority:
            raise NoQuorumError(
                f"{len(active)}/{len(registered)} active:"
                f" majority ({majority}) not reached -"
                " failover refused to avoid split-brain"
            )
        candidates = [
            n
            for n in active
            if n.node_id != failed_primary
            and n.role
            in (NodeRole.COORDINATOR, NodeRole.WORKER)
        ]
        if not candidates:
            raise NoQuorumError(
                "no eligible candidate node available"
            )
        candidates.sort(key=lambda n: n.node_id)
        elected = candidates[0]
        self._audit.append(
            event_type=EVENT_FAILOVER,
            actor="failover-coordinator",
            subject=elected.node_id,
            payload={
                "failed_primary": failed_primary,
                "active": len(active),
                "registered": len(registered),
            },
        )
        return elected.node_id

    def has_quorum(self) -> bool:
        registered = self._cluster.all_nodes()
        if not registered:
            return False
        active = self._cluster.active_nodes()
        return len(active) >= len(registered) // 2 + 1
