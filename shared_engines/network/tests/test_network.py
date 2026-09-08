from __future__ import annotations

from pathlib import Path

import pytest

from shared_engines.audit.chain import AuditTrail
from shared_engines.common.clocks import FrozenClock
from shared_engines.identity.contracts import IdentityKind
from shared_engines.identity.engine import IdentityEngine
from shared_engines.network.cluster import (
    ClusterManager,
    NodeRole,
    NodeState,
)
from shared_engines.network.errors import (
    InvalidTransitionError,
    NoQuorumError,
    NodeNotFoundError,
    ReplicationMismatchError,
)
from shared_engines.network.failover import FailoverCoordinator
from shared_engines.network.replication import ReplicationManager
from shared_engines.storage.database import SQLiteAdapter


class _Harness:
    def __init__(self, tmp_path: Path, nodes: int = 3) -> None:
        self.db = SQLiteAdapter(tmp_path / "net.db")
        self.clock = FrozenClock()
        self.audit = AuditTrail(self.db, self.clock)
        from shared_engines.events.contracts import EventCatalog
        from shared_engines.events.outbox import Outbox

        self.outbox = Outbox(self.db, self.clock)
        self.outbox.ensure_schema()
        self.catalog = EventCatalog()
        for event_type in (
            "network.node.joined",
            "network.node.state_changed",
            "network.failover.elected",
            "identity.registered",
            "identity.status_changed",
        ):
            self.catalog.register(event_type)
        self.identity = IdentityEngine(
            db=self.db,
            clock=self.clock,
            audit=self.audit,
            outbox=self.outbox,
            catalog=self.catalog,
        )
        self.cluster = ClusterManager(
            db=self.db,
            clock=self.clock,
            audit=self.audit,
            outbox=self.outbox,
            catalog=self.catalog,
            heartbeat_ttl_seconds=30.0,
        )
        self.replication = ReplicationManager(
            self.db, self.clock
        )
        self.failover = FailoverCoordinator(
            cluster=self.cluster, audit=self.audit
        )
        self.node_ids: list[str] = []
        for index in range(nodes):
            node_identity = self.identity.register_identity(
                kind=IdentityKind.DEVICE,
                display_name=f"node-{index}",
                actor="bootstrap",
            )
            role = (
                NodeRole.COORDINATOR
                if index == 0
                else NodeRole.WORKER
            )
            self.cluster.register_node(
                node_id=node_identity.zid,
                role=role,
                endpoint=f"tcp://node-{index}:9000",
            )
            self.node_ids.append(node_identity.zid)

    def activate_all(self) -> None:
        for node_id in self.node_ids:
            self.cluster.heartbeat(node_id)

    def kill_node(self, node_id: str) -> None:
        """Advances time so ONLY node_id goes stale: the other
        nodes keep heartbeating and stay ACTIVE."""
        others = [n for n in self.node_ids if n != node_id]
        self.clock.advance(31)
        for other in others:
            self.cluster.heartbeat(other)
        detected = self.cluster.detect_failures()
        assert node_id in detected
        self.clock.advance(31)
        for other in others:
            self.cluster.heartbeat(other)
        detected = self.cluster.detect_failures()
        assert node_id in detected

    def kill_all(self) -> None:
        self.clock.advance(31)
        self.cluster.detect_failures()
        self.clock.advance(31)
        self.cluster.detect_failures()

    def close(self) -> None:
        self.db.close()


def test_nodes_register_and_heartbeat_activates(
    tmp_path: Path,
) -> None:
    harness = _Harness(tmp_path)
    nodes = harness.cluster.all_nodes()
    assert len(nodes) == 3
    assert all(n.state is NodeState.JOINING for n in nodes)
    harness.activate_all()
    active = harness.cluster.active_nodes()
    assert len(active) == 3
    assert all(n.state is NodeState.ACTIVE for n in active)
    harness.close()


def test_heartbeat_failure_detection_ladder(
    tmp_path: Path,
) -> None:
    harness = _Harness(tmp_path)
    harness.activate_all()
    node = harness.cluster.active_nodes()[0]
    harness.clock.advance(31)
    expired = harness.cluster.detect_failures()
    assert node.node_id in expired
    suspect = harness.cluster.require(node.node_id)
    assert suspect.state is NodeState.SUSPECT
    harness.clock.advance(31)
    harness.cluster.detect_failures()
    down = harness.cluster.require(node.node_id)
    assert down.state is NodeState.DOWN
    harness.close()


def test_unknown_node_heartbeat_raises(tmp_path: Path) -> None:
    harness = _Harness(tmp_path)
    with pytest.raises(NodeNotFoundError):
        harness.cluster.heartbeat("ZID-ghost")
    harness.close()


def test_failover_with_quorum_elects_new_primary(
    tmp_path: Path,
) -> None:
    harness = _Harness(tmp_path)
    harness.activate_all()
    coordinator_id = harness.node_ids[0]
    harness.kill_node(coordinator_id)
    new_primary = harness.failover.elect_new_primary(
        failed_primary=coordinator_id
    )
    assert new_primary != coordinator_id
    assert new_primary in harness.node_ids[1:]
    assert harness.failover.has_quorum() is True
    assert harness.audit.verify() >= 1
    harness.close()


def test_failover_without_quorum_refused(
    tmp_path: Path,
) -> None:
    harness = _Harness(tmp_path, nodes=3)
    harness.activate_all()
    coordinator_id = harness.node_ids[0]
    harness.kill_all()
    with pytest.raises(NoQuorumError):
        harness.failover.elect_new_primary(
            failed_primary=coordinator_id
        )
    assert harness.failover.has_quorum() is False
    harness.close()


def test_down_node_recovers_through_rejoined(
    tmp_path: Path,
) -> None:
    """DOWN -> (beat) -> REJOINED -> (beat) -> ACTIVE: the
    full recovery cycle of a returned node."""
    harness = _Harness(tmp_path, nodes=3)
    harness.activate_all()
    victim = harness.node_ids[2]
    harness.kill_node(victim)
    assert harness.cluster.require(victim).state is (
        NodeState.DOWN
    )
    harness.cluster.heartbeat(victim)
    rejoined = harness.cluster.require(victim)
    assert rejoined.state is NodeState.REJOINED
    harness.clock.advance(1)
    harness.cluster.heartbeat(victim)
    recovered = harness.cluster.require(victim)
    assert recovered.state is NodeState.ACTIVE
    harness.close()


def test_replication_consistent_and_mismatch(
    tmp_path: Path,
) -> None:
    harness = _Harness(tmp_path)
    harness.activate_all()
    version, state_hash = harness.replication.compute_state_hash()
    report = harness.replication.replicate(
        primary_node="node-primary",
        replica_node="node-replica",
        replica_hash=state_hash,
    )
    assert report.consistent is True
    assert report.state_hash == state_hash
    with pytest.raises(ReplicationMismatchError):
        harness.replication.replicate(
            primary_node="node-primary",
            replica_node="node-replica",
            replica_hash="0" * 64,
        )
    harness.close()


def test_state_hash_changes_when_membership_changes(
    tmp_path: Path,
) -> None:
    harness = _Harness(tmp_path)
    harness.activate_all()
    _, hash_before = harness.replication.compute_state_hash()
    new_identity = harness.identity.register_identity(
        kind=IdentityKind.DEVICE,
        display_name="node-extra",
        actor="bootstrap",
    )
    harness.cluster.register_node(
        node_id=new_identity.zid,
        role=NodeRole.WORKER,
        endpoint="tcp://node-extra:9000",
    )
    _, hash_after = harness.replication.compute_state_hash()
    assert hash_after != hash_before
    harness.close()


def test_cluster_events_in_outbox(tmp_path: Path) -> None:
    from shared_engines.events.contracts import Event

    harness = _Harness(tmp_path)
    collected: list[Event] = []

    def collect(event: Event) -> None:
        collected.append(event)

    harness.outbox.dispatch_pending(collect)
    by_type = {e.event_type for e in collected}
    assert "network.node.joined" in by_type
    joined = [
        e
        for e in collected
        if e.event_type == "network.node.joined"
    ]
    assert len(joined) == 3
    harness.close()


def test_audit_chain_covers_cluster_events(
    tmp_path: Path,
) -> None:
    harness = _Harness(tmp_path)
    harness.activate_all()
    count = harness.audit.verify()
    assert count >= 6
    harness.close()


def test_duplicate_node_registration_rejected(
    tmp_path: Path,
) -> None:
    harness = _Harness(tmp_path, nodes=1)
    node = harness.cluster.all_nodes()[0]
    with pytest.raises(InvalidTransitionError):
        harness.cluster.register_node(
            node_id=node.node_id,
            role=NodeRole.WORKER,
            endpoint="tcp://dupe:9000",
        )
    harness.close()
