"""Typed telemetry errors."""
from __future__ import annotations

from shared_engines.common.errors import EngineError, ValidationError


class TelemetryError(EngineError):
    """Base for telemetry failures."""


class InvalidMetricError(TelemetryError, ValidationError):
    """A metric name or value failed validation."""
