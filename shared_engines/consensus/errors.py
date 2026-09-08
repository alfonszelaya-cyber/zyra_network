"""Typed consensus errors."""
from __future__ import annotations

from shared_engines.common.errors import (
    EngineError,
)


class ConsensusError(EngineError):
    """Base consensus error."""


class AlreadyVotedError(ConsensusError):
    """Voter already voted in this term."""


class LeaseHeldError(ConsensusError):
    """Lease held by another member."""


class NoLeaseError(ConsensusError):
    """No current lease for the resource."""
