from __future__ import annotations

from collections import Counter
from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class ConsensusResult:
    reached: bool
    value: object | None
    votes: int
    required: int


class QuorumConsensus:
    """Deterministic majority/quorum evaluator."""

    def __init__(self, participants: int) -> None:
        if participants <= 0:
            raise ValueError("Participants must be positive")

        self.participants = participants
        self.required = participants // 2 + 1

    def evaluate(self, values: list[object]) -> ConsensusResult:
        if not values:
            return ConsensusResult(
                reached=False,
                value=None,
                votes=0,
                required=self.required,
            )

        counts = Counter(values)
        value, votes = counts.most_common(1)[0]

        return ConsensusResult(
            reached=votes >= self.required,
            value=value if votes >= self.required else None,
            votes=votes,
            required=self.required,
        )


__all__ = ["ConsensusResult", "QuorumConsensus"]
