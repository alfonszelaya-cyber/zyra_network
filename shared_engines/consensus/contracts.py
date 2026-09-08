"""Consensus contracts."""
from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class LeaseState:
    """Current lease of a resource."""

    resource: str
    holder_id: str
    fencing_token: int
    expires_at: float
