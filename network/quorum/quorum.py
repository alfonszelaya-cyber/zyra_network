"""
Production quorum calculation.

This module calculates quorum from an explicitly supplied
membership set. It does not implement consensus.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from threading import RLock


class QuorumDecision(str, Enum):
    ACHIEVED = "achieved"
    NOT_ACHIEVED = "not_achieved"
    INVALID = "invalid"


@dataclass(frozen=True, slots=True)
class QuorumResult:
    total: int
    votes: int
    required: int
    decision: QuorumDecision

    @property
    def achieved(self) -> bool:
        return (
            self.decision
            is QuorumDecision.ACHIEVED
        )


class QuorumGroup:
    """
    Thread-safe membership and quorum calculator.

    Majority quorum is floor(total / 2) + 1 unless an explicit
    threshold is configured.
    """

    def __init__(
        self,
        *,
        threshold: int | None = None,
    ) -> None:

        if (
            threshold is not None
            and threshold <= 0
        ):
            raise ValueError(
                "threshold must be positive"
            )

        self._threshold = threshold
        self._members: set[str] = set()
        self._lock = RLock()

    def add(
        self,
        member_id: str,
    ) -> None:

        member_id = member_id.strip()

        if not member_id:
            raise ValueError(
                "member_id cannot be empty"
            )

        with self._lock:
            self._members.add(
                member_id
            )

    def remove(
        self,
        member_id: str,
    ) -> bool:

        with self._lock:
            if member_id.strip() not in self._members:
                return False

            self._members.remove(
                member_id.strip()
            )

            return True

    def members(
        self,
    ) -> tuple[str, ...]:

        with self._lock:
            return tuple(
                sorted(
                    self._members
                )
            )

    def required(
        self,
    ) -> int:

        with self._lock:
            total = len(
                self._members
            )

            if total == 0:
                return 0

            if self._threshold is not None:
                return min(
                    self._threshold,
                    total,
                )

            return (
                total // 2
            ) + 1

    def evaluate(
        self,
        voters: set[str] | frozenset[str],
    ) -> QuorumResult:

        if not isinstance(
            voters,
            (set, frozenset),
        ):
            raise TypeError(
                "voters must be set or frozenset"
            )

        with self._lock:
            total = len(
                self._members
            )

            valid_voters = (
                voters
                & self._members
            )

            votes = len(
                valid_voters
            )

            required = self.required()

            if total == 0:
                decision = (
                    QuorumDecision.INVALID
                )

            elif votes >= required:
                decision = (
                    QuorumDecision.ACHIEVED
                )

            else:
                decision = (
                    QuorumDecision.NOT_ACHIEVED
                )

            return QuorumResult(
                total=total,
                votes=votes,
                required=required,
                decision=decision,
            )


__all__ = [
    "QuorumDecision",
    "QuorumResult",
    "QuorumGroup",
]
