"""Search contracts."""
from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class SearchHit:
    """One ranked result from one source."""

    source: str
    ref_id: str
    title: str
    snippet: str
    score: int
