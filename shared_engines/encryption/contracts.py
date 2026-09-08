"""Encryption engine contracts."""
from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class KeyRecord:
    """One durable key-encryption-key."""

    key_id: str
    version: int
    state: str
    created_at: float
    retired_at: float | None
