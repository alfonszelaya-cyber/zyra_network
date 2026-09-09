"""Typed supervisor errors."""
from __future__ import annotations

from shared_engines.common.errors import (
    EngineError,
)


class UnknownComponentError(EngineError):
    """Component not registered."""


class QuarantinedError(EngineError):
    """Component exceeded its restart budget
    and is quarantined."""
