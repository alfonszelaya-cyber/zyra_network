"""System health reporter: one view of the whole Network."""
from __future__ import annotations

from dataclasses import dataclass

from shared_engines.common.clocks import Clock
from shared_engines.network.cluster import ClusterManager
from shared_engines.observability.health import HealthRegistry
from shared_engines.telemetry.collector import TelemetryCollector


@dataclass(frozen=True)
class SystemReport:
    overall_status: str
    components_detail: tuple[str, ...]
    cluster_nodes_active: int
    cluster_nodes_total: int
    recent_event_count: int


class SystemHealthReporter:
    """Aggregates component health + cluster + telemetry."""

    def __init__(
        self,
        *,
        registry: HealthRegistry,
        cluster: ClusterManager,
        telemetry: TelemetryCollector,
        clock: Clock,
    ) -> None:
        self._registry = registry
        self._cluster = cluster
        self._telemetry = telemetry
        self._clock = clock

    def report(self) -> SystemReport:
        overall = self._registry.overall()
        components = self._registry.snapshot()
        all_nodes = self._cluster.all_nodes()
        active = self._cluster.active_nodes()
        recent = self._telemetry.query_events(limit=100)
        return SystemReport(
            overall_status=overall.status.value,
            components_detail=tuple(
                f"{c.component}:{c.status.value}"
                for c in components
            ),
            cluster_nodes_active=len(active),
            cluster_nodes_total=len(all_nodes),
            recent_event_count=len(recent),
        )
