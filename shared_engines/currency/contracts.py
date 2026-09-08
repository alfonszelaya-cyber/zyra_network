"""Versioned currency contracts: Money, pairs, quotes.

Money accepts Decimal ONLY: binary floats are rejected at
construction because their representation error is exactly
the class of financial bug this engine prevents.
"""
from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal

from shared_engines.common.errors import ValidationError
from shared_engines.common.validation import require_non_empty_str

CURRENCY_CONTRACT_VERSION = 1


@dataclass(frozen=True)
class Money:
    amount: Decimal
    currency: str

    def __post_init__(self) -> None:
        if not isinstance(self.amount, Decimal):
            raise ValidationError(
                "Money amount must be Decimal (build from str)"
            )
        if not self.amount.is_finite() or self.amount < 0:
            raise ValidationError(
                "Money amount must be finite and non-negative"
            )
        require_non_empty_str(self.currency, "currency")


@dataclass(frozen=True)
class CurrencyPair:
    base: str
    quote: str

    def __post_init__(self) -> None:
        require_non_empty_str(self.base, "base")
        require_non_empty_str(self.quote, "quote")
        if self.base == self.quote:
            raise ValidationError("base and quote must differ")

    @property
    def normalized(self) -> str:
        return f"{self.base}/{self.quote}"


@dataclass(frozen=True)
class Quote:
    pair: CurrencyPair
    rate: Decimal
    quoted_at: float
    expires_at: float
    source: str

    def __post_init__(self) -> None:
        if not isinstance(self.rate, Decimal):
            raise ValidationError("rate must be Decimal")
        if not self.rate.is_finite() or self.rate <= 0:
            raise ValidationError("rate must be positive")
        if self.expires_at <= self.quoted_at:
            raise ValidationError("quote window is empty")


@dataclass(frozen=True)
class SignedQuote:
    quote: Quote
    issuer_zid: str
    signature: bytes
    signer_public_pem: bytes
    contract_version: int = CURRENCY_CONTRACT_VERSION
