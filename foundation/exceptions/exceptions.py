from __future__ import annotations


class FoundationError(Exception):
    """Base exception for the ZYRA foundation layer."""


class ConfigurationError(FoundationError):
    """Invalid or incomplete system configuration."""


class ValidationError(FoundationError):
    """Domain or structural validation failure."""


class StateError(FoundationError):
    """Invalid state transition or state operation."""


class RegistryError(FoundationError):
    """Registry operation failure."""


class SecurityError(FoundationError):
    """Foundation security boundary violation."""


class LifecycleError(FoundationError):
    """Invalid lifecycle operation."""


class ContractError(FoundationError):
    """Contract violation between system components."""


class NotFoundError(FoundationError):
    """Requested foundation resource does not exist."""


class ConflictError(FoundationError):
    """Operation conflicts with current system state."""


__all__ = [
    "FoundationError",
    "ConfigurationError",
    "ValidationError",
    "StateError",
    "RegistryError",
    "SecurityError",
    "LifecycleError",
    "ContractError",
    "NotFoundError",
    "ConflictError",
]
