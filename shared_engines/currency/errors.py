"""Typed currency errors."""
from __future__ import annotations

from shared_engines.common.errors import (
    EngineError,
    NotFoundError,
    ProviderTransientError,
    ValidationError,
)


class CurrencyError(EngineError):
    """Base for currency engine failures."""


class UnknownCurrencyError(CurrencyError, NotFoundError):
    """The currency code is not in the registry."""


class InvalidRateError(CurrencyError, ValidationError):
    """A rate is not a positive finite decimal."""


class RateUnavailableError(CurrencyError, ProviderTransientError):
    """No provider could quote the pair."""


class StaleRateError(CurrencyError, ValidationError):
    """The only stored quote is beyond the max age."""


class QuoteExpiredError(CurrencyError, ValidationError):
    """A signed quote past its validity window."""


class NoRouteError(CurrencyError, NotFoundError):
    """No direct or bridge route exists for the pair."""
