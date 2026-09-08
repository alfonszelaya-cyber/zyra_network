"""Reputation policy: explicit, inspectable rules.

Score is NEVER a magic increment: every event
contributes weight * sign, decayed by a half-life.
The policy is a frozen value injected at
construction, so different deployments can use
different rules while the arithmetic stays
transparent and auditable.
"""
from __future__ import annotations

from dataclasses import dataclass

from shared_engines.common.validation import (
    require_positive_number,
)


@dataclass(frozen=True)
class ReputationPolicy:
    """Scoring rules (all positive numbers)."""

    weight_per_event: float = 10.0
    half_life_seconds: float = 100.0

    def __post_init__(self) -> None:
        require_positive_number(
            self.weight_per_event,
            "weight_per_event",
        )
        require_positive_number(
            self.half_life_seconds,
            "half_life_seconds",
        )

    def decay_factor(
        self,
        *,
        age_seconds: float,
    ) -> float:
        """0.5 ** (age / half_life): fresh
        evidence counts fully; old evidence
        fades. float() wrapping because
        float ** float is typed Any in the
        stdlib stubs (may be complex)."""
        if age_seconds <= 0.0:
            return 1.0
        exponent = (
            -age_seconds
            / self.half_life_seconds
        )
        return float(2.0**exponent)
