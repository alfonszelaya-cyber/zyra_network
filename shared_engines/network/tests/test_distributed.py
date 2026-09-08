"""Full distributed-network demonstrations over one shared
authority DB: 3 nodes with real ZIDs, replication checks,
coordinator failure with quorum failover, node recovery,
partition refusal (anti-split-brain), all audited and
visible in telemetry."""
from __future__ import annotations

from pathlib import Path

import pytest

from shared_engines.audit.chain import AuditTrail
from shared_engines.common.clocks import FrozenClock
from shared_engines.events.contracts import EventCatalog
from shared_engines.events.outbox import Outbox
from shared_engines.identity.contracts import IdentityKind
from shared_engines.identity.engine import IdentityEngine
from shared_engines.network.cluster import (
    ClusterManager,
    NodeRole,
    NodeState,
)
from shared_engines.network.errors import NoQuorumError
from shared_engines.network.failover import FailoverCoordinator
from shared_engines.network.replication import ReplicationManager
from shared_engines.storage.database import SQLiteAdapter
from shared_engines.telemetry.collector import TelemetryCollector


class DistributedNetwork:
    """3-node network over one durable authority store."""

    def __init__(self, tmp_path: Path) -> None:
        self.db = SQLiteAdapter(tmp_path / "cluster.db")
        self.clock = FrozenClock()
        self.audit = AuditTrail(self.db, self.clock)
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
            cluster=self.cluster,
            audit=self.audit,
            outbox=self.outbox,
            clock=self.clock,
        )
        self.telemetry = TelemetryCollector(
            self.db, self.clock
        )
        self.node_ids: list[str] = []
        for index in range(3):
            node_identity = self.identity.register_identity(
                kind=IdentityKind.DEVICE,
                display_name=f"zyra-node-{index}",
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
                endpoint=(
                    f"tcp://zyra-node-{index}:9000"
                ),
            )
            self.node_ids.append(node_identity.zid)

    def beat(self, node_id: str) -> None:
        self.cluster.heartbeat(node_id)

    def beat_all(self) -> None:
        for node_id in self.node_ids:
            self.cluster.heartbeat(node_id)

    def beat_except(self, dead: str) -> None:
        for node_id in self.node_ids:
            if node_id != dead:
                self.cluster.heartbeat(node_id)

    def sync_replicas(self) -> None:
        _, state_hash = (
            self.replication.compute_state_hash()
        )
        self.replication.replicate(
            primary_node=self.node_ids[0],
            replica_node=self.node_ids[1],
            replica_hash=state_hash,
        )
        self.replication.replicate(
            primary_node=self.node_ids[0],
            replica_node=self.node_ids[2],
            replica_hash=state_hash,
        )

    def ingest_telemetry(self) -> int:
        return self.telemetry.ingest_outbox(self.outbox)

    def close(self) -> None:
        self.db.close()


def test_demo_1_three_nodes_join_and_synchronize(
    tmp_path: Path,
) -> None:
    net = DistributedNetwork(tmp_path)
    try:
        net.beat_all()
        active = net.cluster.active_nodes()
        assert len(active) == 3
        assert active[0].state is NodeState.ACTIVE
        net.sync_replicas()
        report = net.replication.replicate(
            primary_node=net.node_ids[0],
            replica_node=net.node_ids[1],
            replica_hash=(
                net.replication.compute_state_hash()[1]
            ),
        )
        assert report.consistent is True
        assert net.audit.verify() >= 6
    finally:
        net.close()


def test_demo_2_coordinator_fails_quorum_failover(
    tmp_path: Path,
) -> None:
    net = DistributedNetwork(tmp_path)
    try:
        net.beat_all()
        coordinator = net.node_ids[0]
        net.clock.advance(31)
        net.beat_except(coordinator)
        detected = net.cluster.detect_failures()
        assert coordinator in detected
        assert net.cluster.require(
            coordinator
        ).state is NodeState.SUSPECT
        net.clock.advance(31)
        net.beat_except(coordinator)
        net.cluster.detect_failures()
        assert net.cluster.require(
            coordinator
        ).state is NodeState.DOWN
        assert net.failover.has_quorum() is True
        new_primary = net.failover.elect_new_primary(
            failed_primary=coordinator
        )
        assert new_primary in net.node_ids[1:]
        net.beat_all()
        net.clock.advance(1)
        net.ingest_telemetry()
        events = net.telemetry.query_events(
            event_type="network.failover.elected"
        )
        assert len(events) >= 1
        events_state = net.telemetry.query_events(
            event_type="network.node.state_changed"
        )
        assert len(events_state) >= 1
    finally:
        net.close()


def test_demo_3_failed_node_returns_and_resyncs(
    tmp_path: Path,
) -> None:
    net = DistributedNetwork(tmp_path)
    try:
        net.beat_all()
        worker = net.node_ids[2]
        net.clock.advance(31)
        net.beat_except(worker)
        net.cluster.detect_failures()
        net.clock.advance(31)
        net.beat_except(worker)
        net.cluster.detect_failures()
        assert net.cluster.require(worker).state is (
            NodeState.DOWN
        )
        net.cluster.heartbeat(worker)
        assert net.cluster.require(worker).state is (
            NodeState.REJOINED
        )
        net.clock.advance(1)
        net.cluster.heartbeat(worker)
        assert net.cluster.require(worker).state is (
            NodeState.ACTIVE
        )
        _, state_hash = (
            net.replication.compute_state_hash()
        )
        report = net.replication.replicate(
            primary_node=net.node_ids[0],
            replica_node=worker,
            replica_hash=state_hash,
        )
        assert report.consistent is True
        net.ingest_telemetry()
        rejoin_events = net.telemetry.query_events(
            event_type="network.node.state_changed"
        )
        assert len(rejoin_events) >= 1
    finally:
        net.close()


def test_demo_4_partition_refuses_split_brain(
    tmp_path: Path,
) -> None:
    net = DistributedNetwork(tmp_path)
    try:
        net.beat_all()
        coordinator = net.node_ids[0]
        net.clock.advance(31)
        net.cluster.detect_failures()
        net.clock.advance(31)
        net.cluster.detect_failures()
        for node_id in net.node_ids[1:]:
            net.clock.advance(31)
            net.cluster.detect_failures()
            net.clock.advance(31)
            net.cluster.detect_failures()
        assert net.failover.has_quorum() is False
        with pytest.raises(NoQuorumError):
            net.failover.elect_new_primary(
                failed_primary=coordinator
            )
        assert net.audit.verify() >= 1
        net.ingest_telemetry()
    finally:
        net.close()


def test_demo_5_full_lifecycle_audit_and_telemetry(
    tmp_path: Path,
) -> None:
    net = DistributedNetwork(tmp_path)
    try:
        net.beat_all()
        coordinator = net.node_ids[0]
        net.clock.advance(31)
        net.beat_except(coordinator)
        net.cluster.detect_failures()
        net.clock.advance(31)
        net.beat_except(coordinator)
        net.cluster.detect_failures()
        new_primary = net.failover.elect_new_primary(
            failed_primary=coordinator
        )
        net.clock.advance(1)
        net.cluster.heartbeat(coordinator)
        net.cluster.heartbeat(new_primary)
        net.ingest_telemetry()
        assert net.audit.verify() >= 8
        joined = net.telemetry.query_events(
            event_type="network.node.joined"
        )
        assert len(joined) == 3
        failover_events = net.telemetry.query_events(
            event_type="network.failover.elected"
        )
        assert len(failover_events) >= 1
        # Identity registrations are EVENTS in
        # telemetry_events (not metrics), so the
        # registered count is queried from the event
        # stream.
        registered_events = net.telemetry.query_events(
            event_type="identity.registered"
        )
        assert len(registered_events) >= 3
    finally:
        net.close()
