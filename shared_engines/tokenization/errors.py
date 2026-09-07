"""Typed tokenization errors."""
from __future__ import annotations

from shared_engines.common.errors import (
    ConfigurationError,
    EngineError,
    NotFoundError,
    ValidationError,
)


class TokenizationError(EngineError):
    """Base for token engine failures."""


class InsufficientBalanceError(TokenizationError, ValidationError):
    """The account cannot cover the requested amount."""


class UnknownRuleError(TokenizationError, NotFoundError):
    """No emission rule exists for the given id/activity."""


class RuleInactiveError(TokenizationError, ValidationError):
    """The emission rule exists but is disabled."""


class EmissionCapExceededError(TokenizationError, ValidationError):
    """The emission would exceed a daily or lifetime cap."""


class UnknownItemError(TokenizationError, NotFoundError):
    """No redemption item exists for the given id."""


class ItemInactiveError(TokenizationError, ValidationError):
    """The redemption item exists but is disabled."""


class DuplicateRuleError(TokenizationError, ConfigurationError):
    """An emission rule already exists for this activity."""
