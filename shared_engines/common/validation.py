"""Fail-fast validation helpers."""
from __future__ import annotations

import math
from collections.abc import Sequence

from shared_engines.common.errors import ConfigurationError, ValidationError


def _raise(message: str, config: bool) -> None:
    if config:
        raise ConfigurationError(message)
    raise ValidationError(message)


def require_non_empty_str(
    value: str, name: str, *, config: bool = False
) -> str:
    if not isinstance(value, str) or not value.strip():
        _raise(f"{name} must be a non-empty string", config)
    return value


def require_int_range(
    value: int, name: str, minimum: int, maximum: int,
    *, config: bool = False,
) -> int:
    if not isinstance(value, int) or isinstance(value, bool):
        _raise(f"{name} must be an integer", config)
    if not minimum <= value <= maximum:
        _raise(f"{name} must be in [{minimum}, {maximum}]", config)
    return value


def require_positive_number(
    value: float, name: str, *, config: bool = False
) -> float:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        _raise(f"{name} must be a number", config)
    if not math.isfinite(value) or value <= 0:
        _raise(f"{name} must be a positive finite number", config)
    return float(value)


def require_one_of(
    value: str, allowed: Sequence[str], name: str,
    *, config: bool = False,
) -> str:
    if value not in allowed:
        _raise(f"{name} must be one of {sorted(allowed)}", config)
    return value
