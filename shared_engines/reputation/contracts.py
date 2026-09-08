"""Reputation contracts."""
from __future__ import annotations

from dataclasses import dataclass

KIND_POSITIVE = "positive"
KIND_NEGATIVE = "negative"

EVENT_KINDS = (
    KIND_POSITIVE,
    KIND_NEGATIVE,
)


@dataclass(frozen=True)
class ReputationEvent:
    """One evidence-backed reputation event."""

    event_id: str
    seq: int
    subject_zid: str
    actor_zid: str
    kind: str
    weight: float
    evidence_sha: str
    proof_id: str
    created_at: float


@dataclass(frozen=True)
class ReputationSummary:
    """Computed, evidence-backed state."""

    subject_zid: str
    score: int
    positive_events: int
    negative_events: int
    last_event_at: float | None
