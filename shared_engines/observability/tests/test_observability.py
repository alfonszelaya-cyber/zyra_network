from __future__ import annotations

import pytest

from shared_engines.common.errors import ConfigurationError
from shared_engines.observability.backend import (
    CompositeMetrics,
    InMemoryMetrics,
)
from shared_engines.observability.health import (
    ComponentHealth,
    HealthRegistry,
    HealthStatus,
)


class _Up:
    def check_health(self) -> ComponentHealth:
        return ComponentHealth("up", HealthStatus.HEALTHY, "ok")


class _Degraded:
    def check_health(self) -> ComponentHealth:
        return ComponentHealth("dep", HealthStatus.DEGRADED, "slow")


class _Broken:
    def check_health(self) -> ComponentHealth:
        raise RuntimeError("boom")


def test_registry_aggregates_worst_status() -> None:
    registry = HealthRegistry()
    registry.register("a", _Up())
    registry.register("b", _Broken())
    overall = registry.overall()
    assert overall.status is HealthStatus.UNHEALTHY
    assert overall.detail == "1/2 components healthy"


def test_registry_reports_degraded_middle() -> None:
    registry = HealthRegistry()
    registry.register("a", _Up())
    registry.register("b", _Degraded())
    assert registry.overall().status is HealthStatus.DEGRADED


def test_duplicate_registration_rejected() -> None:
    registry = HealthRegistry()
    registry.register("a", _Up())
    with pytest.raises(ConfigurationError):
        registry.register("a", _Up())


def test_metrics_record_and_fan_out() -> None:
    memory = InMemoryMetrics()
    composite = CompositeMetrics((memory,))
    composite.increment("test.counter")
    composite.increment("test.counter", tags={"r": "ok"})
    composite.observe("latency", 0.25)
    assert memory.counter_value("test.counter") == 1
    assert memory.counter_value("test.counter", {"r": "ok"}) == 1
    assert memory.values("latency") == (0.25,)
