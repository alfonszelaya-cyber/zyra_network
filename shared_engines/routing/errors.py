"""Typed routing errors."""
from __future__ import annotations

from shared_engines.common.errors import (
    NotFoundError,
)


class NoRouteError(NotFoundError):
    """No active route for the key."""
