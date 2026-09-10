from __future__ import annotations

import tempfile
from pathlib import Path

from observability import (
    AlertRule,
    HealthState,
    IncidentState,
    MetricKind,
    MetricRegistry,
    MetricSample,
    ObservationContext,
    ObservationManager,
    ObservationStore,
    Severity,
)


def test_context_trace_propagation():
    root = ObservationContext.create(
        component="zyra.network",
        operation="root",
        labels={"environment": "test"},
    )

    child = root.child("child")

    assert child.trace_id == root.trace_id
    assert (
        child.correlation_id
        == root.correlation_id
    )
    assert (
        child.parent_span_id
        == root.span_id
    )
    assert child.span_id != root.span_id


def test_metric_counter():
    registry = MetricRegistry()

    first = registry.counter(
        "requests_total",
        2,
        {"service": "test"},
    )

    second = registry.counter(
        "requests_total",
        3,
        {"service": "test"},
    )

    samples = registry.query(
        "requests_total"
    )

    assert first.value == 2
    assert second.value == 3
    assert len(samples) == 2


def test_metric_gauge():
    registry = MetricRegistry()

    registry.gauge(
        "load",
        75,
    )

    result = registry.query(
        "load"
    )

    assert len(result) == 1
    assert result[0].value == 75


def test_alert_fires_and_resolves():
    manager = ObservationManager()

    manager.alerts.register_rule(
        AlertRule(
            rule_id="load-alert",
            name="Load",
            metric_name="load",
            threshold=80,
            operator=">",
            severity=Severity.WARNING,
        )
    )

    manager.start()

    firing = manager.record_metric(
        MetricSample.create(
            name="load",
            kind=MetricKind.GAUGE,
            value=90,
        )
    )

    assert len(firing) == 1
    assert (
        firing[0].state.value
        == "firing"
    )

    resolved = manager.record_metric(
        MetricSample.create(
            name="load",
            kind=MetricKind.GAUGE,
            value=40,
        )
    )

    assert len(resolved) == 1
    assert (
        resolved[0].state.value
        == "resolved"
    )


def test_health_check():
    manager = ObservationManager()

    manager.health.register(
        "database",
        lambda: True,
    )

    result = manager.health.check(
        "database"
    )

    assert (
        result.state
        is HealthState.HEALTHY
    )


def test_health_failure():
    manager = ObservationManager()

    def failing_check():
        raise RuntimeError("failure")

    manager.health.register(
        "database",
        failing_check,
    )

    result = manager.health.check(
        "database"
    )

    assert (
        result.state
        is HealthState.UNHEALTHY
    )


def test_incident_lifecycle():
    manager = ObservationManager()

    incident = manager.incidents.create(
        "Production degradation",
        severity=Severity.ERROR,
    )

    assert (
        incident.state
        is IncidentState.OPEN
    )

    incident.transition(
        IncidentState.MITIGATING
    )

    assert (
        incident.state
        is IncidentState.MITIGATING
    )

    incident.transition(
        IncidentState.RESOLVED
    )

    assert (
        incident.state
        is IncidentState.RESOLVED
    )


def test_durable_storage():
    with tempfile.TemporaryDirectory() as directory:
        path = (
            Path(directory)
            / "observations.jsonl"
        )

        store = ObservationStore(
            path,
            max_records=100,
            fsync=False,
        )

        store.append(
            {
                "type": "event",
                "value": 123,
            }
        )

        assert store.count() == 1

        records = store.read_all()

        assert len(records) == 1
        assert (
            records[0]["value"]
            == 123
        )


def test_manager_lifecycle():
    manager = ObservationManager()

    assert (
        manager.status()["state"]
        == "created"
    )

    manager.start()

    assert (
        manager.status()["state"]
        == "running"
    )

    manager.stop()

    assert (
        manager.status()["state"]
        == "stopped"
    )


def test_persistent_manager():
    with tempfile.TemporaryDirectory() as directory:
        path = (
            Path(directory)
            / "observations.jsonl"
        )

        manager = ObservationManager(
            storage_path=path,
        )

        manager.start()

        sample = MetricSample.create(
            name="requests",
            kind=MetricKind.COUNTER,
            value=1,
        )

        manager.record_metric(
            sample
        )

        assert (
            manager.storage is not None
        )

        assert (
            manager.storage.count()
            >= 1
        )


def test_public_compatibility_alias():
    import observability

    assert hasattr(
        observability,
        "ObservationError",
    )


def test_component_registry():
    manager = ObservationManager()

    manager.registry.register(
        "zyra.network",
        kind="network",
        metadata={
            "layer": "cross-cutting",
        },
    )

    component = (
        manager.registry.get(
            "zyra.network"
        )
    )

    assert component is not None
    assert (
        component["kind"]
        == "network"
    )
