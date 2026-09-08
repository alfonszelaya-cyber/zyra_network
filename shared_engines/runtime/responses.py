"""HTTP response envelope and typed-error mapping."""
from __future__ import annotations

from shared_engines.common.errors import (
    BackpressureError,
    ConfigurationError,
    EngineError,
    PolicyViolation,
    RecoveryRequired,
    ValidationError,
)
from shared_engines.currency.errors import (
    NoRouteError,
    QuoteExpiredError,
    RateUnavailableError,
    StaleRateError,
    UnknownCurrencyError,
)
from shared_engines.identity.errors import (
    IdentityAlreadyExistsError,
    IdentityNotFoundError,
    InvalidTransitionError,
)
from shared_engines.tokenization.errors import (
    DuplicateRuleError,
    EmissionCapExceededError,
    InsufficientBalanceError,
    ItemInactiveError,
    RuleInactiveError,
    UnknownItemError,
    UnknownRuleError,
)
from shared_engines.verification.errors import (
    AttestationNotFoundError,
    CredentialNotFoundError,
    MediaNotFoundError,
    TamperDetectedError,
)


class ApiError(Exception):
    """Explicit API failure with a stable status and code."""

    def __init__(self, status: int, code: str, message: str) -> None:
        super().__init__(message)
        self.status = status
        self.code = code
        self.message = message


_NOT_FOUND_ERRORS = (
    IdentityNotFoundError,
    MediaNotFoundError,
    AttestationNotFoundError,
    CredentialNotFoundError,
    UnknownRuleError,
    UnknownItemError,
    UnknownCurrencyError,
    NoRouteError,
)

_CONFLICT_ERRORS = (
    InvalidTransitionError,
    TamperDetectedError,
    IdentityAlreadyExistsError,
    InsufficientBalanceError,
    EmissionCapExceededError,
    RuleInactiveError,
    ItemInactiveError,
    StaleRateError,
    QuoteExpiredError,
    DuplicateRuleError,
)


def map_engine_error(exc: EngineError) -> ApiError:
    """Maps typed engine errors to stable HTTP semantics."""
    if isinstance(exc, _NOT_FOUND_ERRORS):
        return ApiError(404, "not_found", str(exc))
    if isinstance(exc, _CONFLICT_ERRORS):
        return ApiError(409, "conflict", str(exc))
    if isinstance(exc, PolicyViolation):
        return ApiError(403, "forbidden", str(exc))
    if isinstance(exc, ValidationError):
        return ApiError(400, "invalid_request", str(exc))
    if isinstance(
        exc, (BackpressureError, RateUnavailableError)
    ):
        return ApiError(503, "unavailable", str(exc))
    if isinstance(exc, (RecoveryRequired, ConfigurationError)):
        return ApiError(
            500, "internal_error", "internal state error"
        )
    return ApiError(500, "internal_error", "internal error")
