"""Quorum-gated failover: no split-brain, ever."""
from __future__ import annotations

import hashlib

from shared_engines.audit.chain import AuditTrail
from shared_engines.common.clocks import Clock
from shared_engines.common.identifiers import new_id
from shared_engines.common.serialization import (
    canonical_json_dumps,
)
from shared_engines.common.validation import (
    require_non_empty_str,
)
from shared_engines.events.contracts import Event
from shared_engines.events.outbox import Outbox
from shared_engines.network.cluster import (
    ClusterManager,
    NodeRole,
)
from shared_engines.network.errors import NoQuorumError

EVENT_FAILOVER = "network.failover.elected"


class FailoverCoordinator:
    """Elects a new primary under quorum.

    The election is audited always, and when an Outbox
    is provided the elected event is enqueued durably,
    closing the flow: Failover -> Audit -> Outbox ->
    Telemetry.
    """

    def __init__(
        self,
        *,
        cluster: ClusterManager,
        audit: AuditTrail,
        outbox: Outbox | None = None,
        clock: Clock | None = None,
    ) -> None:
        self._cluster = cluster
        self._audit = audit
        self._outbox = outbox
        self._clock = clock

    def elect_new_primary(
        self, *, failed_primary: str
    ) -> str:
        require_non_empty_str(
            failed_primary, "failed_primary"
        )
        registered = self._cluster.all_nodes()
        if len(registered) == 0:
            raise NoQuorumError("cluster is empty")
        active = self._cluster.active_nodes()
        majority = len(registered) // 2 + 1
        if len(active) < majority:
            raise NoQuorumError(
                f"{len(active)}/{len(registered)}"
                f" active: majority ({majority})"
                " not reached - failover refused"
                " to avoid split-brain"
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
        self._publish(
            elected=elected.node_id,
            failed_primary=failed_primary,
            active=len(active),
            registered=len(registered),
        )
        return elected.node_id

    def _publish(
        self,
        *,
        elected: str,
        failed_primary: str,
        active: int,
        registered: int,
    ) -> None:
        """Durably enqueue the elected event (if wired)."""
        if self._outbox is None:
            return
        timestamp = (
            self._clock.now()
            if self._clock is not None
            else 0.0
        )
        payload = {
            "failed_primary": failed_primary,
            "elected": elected,
            "active": active,
            "registered": registered,
        }
        event_id = new_id()
        fingerprint_src = canonical_json_dumps(
            {
                "event_id": event_id,
                "event_type": EVENT_FAILOVER,
                "aggregate_id": elected,
                "timestamp": timestamp,
                "payload": payload,
            }
        )
        fingerprint = hashlib.sha256(
            fingerprint_src.encode("utf-8")
        ).hexdigest()
        self._outbox.enqueue(
            Event(
                event_id=event_id,
                event_type=EVENT_FAILOVER,
                aggregate_id=elected,
                schema_version=1,
                envelope_version=1,
                timestamp=timestamp,
                payload=payload,
                fingerprint=fingerprint,
            )
        )

    def has_quorum(self) -> bool:
        registered = self._cluster.all_nodes()
        if not registered:
            return False
        active = self._cluster.active_nodes()
        return len(active) >= len(registered) // 2 + 1
