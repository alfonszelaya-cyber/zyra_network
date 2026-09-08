"""Typed search errors."""
from __future__ import annotations

from shared_engines.common.errors import (
    EngineError,
)


class SearchNotAuthorizedError(EngineError):
    """Querying app is not registered."""


class UnknownSourceError(EngineError):
    """Requested search source does not exist."""
