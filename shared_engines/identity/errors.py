"""Typed identity errors."""
from __future__ import annotations

from shared_engines.common.errors import (
    ConcurrencyError,
    EngineError,
    NotFoundError,
    ValidationError,
)


class IdentityError(EngineError):
    """Base for identity engine failures."""


class IdentityAlreadyExistsError(IdentityError, ConcurrencyError):
    """A ZID collision was detected during registration."""


class InvalidTransitionError(IdentityError, ValidationError):
    """The lifecycle transition is not allowed."""


class IdentityNotFoundError(IdentityError, NotFoundError):
    """No identity exists for the given ZID."""
