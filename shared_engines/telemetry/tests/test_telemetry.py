from __future__ import annotations

from pathlib import Path

import pytest

from shared_engines.audit.chain import AuditTrail
from shared_engines.common.clocks import FrozenClock
from shared_engines.identity.contracts import IdentityKind
from shared_engines.identity.engine import IdentityEngine
from shared_engines.network.cluster import ClusterManager, NodeRole
from shared_engines.observability.health import (
    ComponentHealth,
    HealthRegistry,
    HealthStatus,
)
from shared_engines.events.contracts import EventCatalog
from shared_engines.events.outbox import Outbox
from shared_engines.storage.database import SQLiteAdapter
from shared_engines.telemetry.collector import TelemetryCollector
from shared_engines.telemetry.errors import InvalidMetricError
from shared_engines.telemetry.system_health import (
    SystemHealthReporter,
)


class _StaticHealth:
    def check_health(self) -> ComponentHealth:
        return ComponentHealth(
            "storage", HealthStatus.HEALTHY, "static ok"
        )


class _Harness:
    def __init__(self, tmp_path: Path) -> None:
        self.db = SQLiteAdapter(tmp_path / "tel.db")
        self.clock = FrozenClock()
        self.audit = AuditTrail(self.db, self.clock)
        self.outbox = Outbox(self.db, self.clock)
        self.outbox.ensure_schema()
        self.catalog = EventCatalog()
        for event_type in (
            "network.node.joined",
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
        )
        self.telemetry = TelemetryCollector(self.db, self.clock)
        self.registry = HealthRegistry()

    def ingest_all(self) -> int:
        return self.telemetry.ingest_outbox(self.outbox)

    def close(self) -> None:
        self.db.close()


def test_counter_gauge_timer_persist(tmp_path: Path) -> None:
    harness = _Harness(tmp_path)
    harness.telemetry.counter("identity.registered")
    harness.telemetry.counter("identity.registered")
    harness.telemetry.gauge("cluster.nodes.active", 3.0)
    harness.telemetry.timer("request.latency", 0.25)
    metrics = harness.telemetry.query_metrics(
        "identity.registered"
    )
    assert len(metrics) == 2
    assert all(m.kind == "counter" for m in metrics)
    summary = harness.telemetry.metric_summary(
        "identity.registered"
    )
    assert summary["count"] == 2
    assert summary["total"] == 2.0
    latencies = harness.telemetry.query_metrics(
        "request.latency"
    )
    assert latencies[0].value == 0.25
    harness.close()


def test_outbox_ingested_into_telemetry(tmp_path: Path) -> None:
    harness = _Harness(tmp_path)
    user = harness.identity.register_identity(
        kind=IdentityKind.PERSON,
        display_name="Watched",
        actor="registrar",
    )
    indexed = harness.ingest_all()
    assert indexed >= 1
    events = harness.telemetry.query_events(
        aggregate_id=user.zid
    )
    types = {e["event_type"] for e in events}
    assert "identity.registered" in types
    by_type = harness.telemetry.query_events(
        event_type="identity.registered"
    )
    assert len(by_type) >= 1
    harness.close()


def test_ingest_is_idempotent(tmp_path: Path) -> None:
    harness = _Harness(tmp_path)
    harness.identity.register_identity(
        kind=IdentityKind.PERSON,
        display_name="Once",
        actor="registrar",
    )
    first = harness.ingest_all()
    assert first >= 1
    second = harness.telemetry.ingest_outbox(harness.outbox)
    assert second == 0
    harness.close()


def test_system_report_aggregates_everything(
    tmp_path: Path,
) -> None:
    harness = _Harness(tmp_path)
    harness.identity.register_identity(
        kind=IdentityKind.PERSON,
        display_name="Node Owner",
        actor="bootstrap",
    )
    node_identity = harness.identity.register_identity(
        kind=IdentityKind.DEVICE,
        display_name="node-0",
        actor="bootstrap",
    )
    harness.cluster.register_node(
        node_id=node_identity.zid,
        role=NodeRole.COORDINATOR,
        endpoint="tcp://node-0:9000",
    )
    harness.cluster.heartbeat(node_identity.zid)
    harness.ingest_all()
    harness.registry.register("storage", _StaticHealth())
    reporter = SystemHealthReporter(
        registry=harness.registry,
        cluster=harness.cluster,
        telemetry=harness.telemetry,
        clock=harness.clock,
    )
    report = reporter.report()
    assert report.overall_status == "healthy"
    assert report.cluster_nodes_total >= 1
    assert report.recent_event_count >= 1
    harness.close()


def test_invalid_metric_rejected(tmp_path: Path) -> None:
    harness = _Harness(tmp_path)
    with pytest.raises(InvalidMetricError):
        harness.telemetry.gauge("bad.gauge", -1.0)
    with pytest.raises(InvalidMetricError):
        harness.telemetry.timer("bad.timer", 0.0)
    harness.close()


def test_telemetry_survives_reopen(tmp_path: Path) -> None:
    path = tmp_path / "tel.db"
    db = SQLiteAdapter(path)
    telemetry = TelemetryCollector(db, FrozenClock())
    telemetry.counter("persist.test")
    db.close()
    db2 = SQLiteAdapter(path)
    telemetry2 = TelemetryCollector(db2, FrozenClock())
    records = telemetry2.query_metrics("persist.test")
    assert len(records) == 1
    db2.close()
