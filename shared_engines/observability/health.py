"""Health and readiness contracts.

Component statuses distinguish process health from dependency
availability. Overall status is the worst across registered
components; a crashed check reports unhealthy, never crashes
the registry.
"""
from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from typing import Protocol

from shared_engines.common.errors import ConfigurationError


class HealthStatus(Enum):
    HEALTHY = "healthy"
    DEGRADED = "degraded"
    UNHEALTHY = "unhealthy"


@dataclass(frozen=True)
class ComponentHealth:
    component: str
    status: HealthStatus
    detail: str


class HealthCheck(Protocol):
    def check_health(self) -> ComponentHealth:
        ...


_SEVERITY: dict[HealthStatus, int] = {
    HealthStatus.HEALTHY: 0,
    HealthStatus.DEGRADED: 1,
    HealthStatus.UNHEALTHY: 2,
}


class HealthRegistry:
    def __init__(self) -> None:
        self._checks: dict[str, HealthCheck] = {}

    def register(self, name: str, check: HealthCheck) -> None:
        if name in self._checks:
            raise ConfigurationError(
                f"health check already registered: {name}"
            )
        self._checks[name] = check

    def snapshot(self) -> tuple[ComponentHealth, ...]:
        results: list[ComponentHealth] = []
        for name, check in self._checks.items():
            try:
                results.append(check.check_health())
            except Exception as exc:
                results.append(
                    ComponentHealth(
                        name,
                        HealthStatus.UNHEALTHY,
                        f"check crashed: {type(exc).__name__}",
                    )
                )
        return tuple(results)

    def overall(self) -> ComponentHealth:
        components = self.snapshot()
        if not components:
            return ComponentHealth(
                "overall",
                HealthStatus.UNHEALTHY,
                "no components registered",
            )
        worst = max(components, key=lambda c: _SEVERITY[c.status])
        healthy = sum(
            1 for c in components if c.status is HealthStatus.HEALTHY
        )
        return ComponentHealth(
            "overall",
            worst.status,
            f"{healthy}/{len(components)} components healthy",
        )
