"""Typed hardening errors."""
from __future__ import annotations

from shared_engines.common.errors import (
    EngineError,
    NotFoundError,
    ValidationError,
)


class HardeningError(EngineError):
    """Base for hardening failures."""


class InvalidApiKeyError(HardeningError, ValidationError):
    """The presented API key does not exist or is malformed."""


class ApiKeyRevokedError(HardeningError, ValidationError):
    """The API key was revoked and can no longer be used."""


class ApiKeyNotFoundError(HardeningError, NotFoundError):
    """No API key exists for the given id."""


class RateLimitExceededError(HardeningError, ValidationError):
    """The rate limit for this window was exceeded."""


class SourceLockedError(HardeningError, ValidationError):
    """This source is temporarily locked after failed
    authentication attempts."""
