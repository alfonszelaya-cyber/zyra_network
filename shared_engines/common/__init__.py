"""Zyra foundation primitives."""
from __future__ import annotations

from shared_engines.common.errors import (
    BackpressureError,
    BudgetExceeded,
    ConfigurationError,
    ConcurrencyError,
    EngineError,
    IntegrityError,
    LeaseLost,
    MigrationError,
    NotFoundError,
    PolicyViolation,
    ProviderPermanentError,
    ProviderTransientError,
    RecoveryRequired,
    SerializationError,
    UnsupportedVersionError,
    ValidationError,
)

__all__ = [
    "BackpressureError", "BudgetExceeded", "ConfigurationError",
    "ConcurrencyError", "EngineError", "IntegrityError",
    "LeaseLost", "MigrationError", "NotFoundError",
    "PolicyViolation", "ProviderPermanentError",
    "ProviderTransientError", "RecoveryRequired",
    "SerializationError", "UnsupportedVersionError",
    "ValidationError",
]
