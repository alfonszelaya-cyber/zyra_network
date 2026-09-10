"""ZYRA Network telemetry facade.

The real telemetry engine lives in
``shared_engines.telemetry`` (collector, system
health, errors, tests). This root package is a
thin composition facade: it re-exports the engine
API so external consumers can import from either
path, and exists so the root layout stays stable
for deploy targets. It deliberately contains no
second implementation.
"""
from shared_engines.telemetry.collector import (
    TelemetryCollector,
)
from shared_engines.telemetry.errors import (
    TelemetryError,
)
from shared_engines.telemetry.system_health import (
    SystemHealth,
)

__all__ = [
    "TelemetryCollector",
    "TelemetryError",
    "SystemHealth",
]
