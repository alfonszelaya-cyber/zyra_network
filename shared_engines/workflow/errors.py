"""Typed workflow errors."""
from __future__ import annotations

from shared_engines.common.errors import (
    EngineError,
)


class UnknownWorkflowError(EngineError):
    """Workflow definition not registered."""


class UnknownRunError(EngineError):
    """Workflow run does not exist."""


class InvalidStateError(EngineError):
    """Operation not valid in current run
    state."""
