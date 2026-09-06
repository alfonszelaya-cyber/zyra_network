from ..core import (
    HealthResult,
    HealthState,
)


def aggregate_health(
    results: list[HealthResult],
) -> HealthState:

    if not results:
        return HealthState.UNKNOWN

    states = {
        result.state
        for result in results
    }

    if HealthState.UNHEALTHY in states:
        return HealthState.UNHEALTHY

    if HealthState.DEGRADED in states:
        return HealthState.DEGRADED

    if HealthState.UNKNOWN in states:
        return HealthState.DEGRADED

    return HealthState.HEALTHY


__all__ = [
    "aggregate_health",
]
