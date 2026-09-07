"""Typed error hierarchy."""
from __future__ import annotations


class EngineError(Exception):
    """Base for every engine error."""


class ConfigurationError(EngineError):
    """Unsafe configuration; fail at startup."""


class ValidationError(EngineError):
    """Input failed validation."""


class SerializationError(EngineError):
    """Serialization or parsing failed."""


class IntegrityError(EngineError):
    """Data failed integrity verification."""


class ConcurrencyError(EngineError):
    """Concurrent access conflict."""


class LeaseLost(ConcurrencyError):
    """Fencing token rejected."""


class RecoveryRequired(EngineError):
    """Externally-uncertain outcome."""


class ProviderTransientError(EngineError):
    """Retryable provider failure."""


class ProviderPermanentError(EngineError):
    """Non-retryable provider failure."""


class BackpressureError(EngineError):
    """Bounded queue full."""


class BudgetExceeded(EngineError):
    """Budget or limit exceeded."""


class MigrationError(EngineError):
    """Migration inconsistency."""


class UnsupportedVersionError(EngineError):
    """Incompatible version."""


class NotFoundError(EngineError):
    """Entity does not exist."""


class PolicyViolation(EngineError):
    """Denied by policy."""
