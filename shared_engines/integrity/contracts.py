"""Integrity contracts."""
from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class IntegrityProof:
    """A durable, verifiable content proof."""

    proof_id: str
    subject: str
    algorithm: str
    digest: str
    size_bytes: int
    created_at: float
