"""Typed scalability errors."""
from __future__ import annotations

from shared_engines.common.errors import (
    EngineError,
)


class CapacityNotDefinedError(
    EngineError
):
    """Resource has no registered capacity."""
