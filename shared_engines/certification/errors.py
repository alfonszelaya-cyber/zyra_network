"""Typed certification errors."""
from __future__ import annotations

from shared_engines.common.errors import (
    EngineError,
)


class IssuerNotRegisteredError(EngineError):
    """Entity is not an accredited certifier."""


class ScopeNotAuthorizedError(EngineError):
    """Issuer lacks authority for this scope."""


class CertificateNotFoundError(EngineError):
    """Unknown certificate id."""


class AlreadyRevokedError(EngineError):
    """Certificate was already revoked."""
