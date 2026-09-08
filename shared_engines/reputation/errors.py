"""Typed reputation errors."""
from __future__ import annotations

from shared_engines.common.errors import (
    EngineError,
)


class SelfReputationError(EngineError):
    """An entity cannot rate itself."""


class UnknownEntityError(EngineError):
    """Subject or actor identity unknown."""


class EmptyEvidenceError(EngineError):
    """Evidence bytes are required."""
