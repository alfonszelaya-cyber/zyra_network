from __future__ import annotations

from .identifier import Identifier


def is_valid_identifier(value: str) -> bool:
    """Return True when value is a valid ZYRA identifier."""
    try:
        Identifier(value)
        return True
    except (TypeError, ValueError):
        return False


def require_identifier(
    value: str | Identifier,
) -> Identifier:
    """
    Normalize an identifier and fail immediately when invalid.
    """
    if isinstance(value, Identifier):
        return value

    return Identifier(value)
