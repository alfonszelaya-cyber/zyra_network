"""Shared observability: metrics backends and health checks."""
from __future__ import annotations

from shared_engines.observability.backend import (
    CompositeMetrics,
    InMemoryMetrics,
    MetricsBackend,
    NoopMetrics,
    engine_logger,
)
from shared_engines.observability.health import (
    ComponentHealth,
    HealthCheck,
    HealthRegistry,
    HealthStatus,
)

__all__ = [
    "ComponentHealth", "CompositeMetrics", "HealthCheck",
    "HealthRegistry", "HealthStatus", "InMemoryMetrics",
    "MetricsBackend", "NoopMetrics", "engine_logger",
]
