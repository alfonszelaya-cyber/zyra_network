"""Typed network errors."""
from __future__ import annotations

from shared_engines.common.errors import (
    ConcurrencyError,
    EngineError,
    NotFoundError,
    ValidationError,
)


class NetworkError(EngineError):
    """Base for network layer failures."""


class NodeNotFoundError(NetworkError, NotFoundError):
    """The node is not part of the cluster."""


class NoQuorumError(NetworkError, ConcurrencyError):
    """No majority active: failover refused (no split-brain)."""


class InvalidTransitionError(NetworkError, ValidationError):
    """The node state transition is not allowed."""


class ReplicationMismatchError(NetworkError, ValidationError):
    """Replica state hash differs from primary."""
