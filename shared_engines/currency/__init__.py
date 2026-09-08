"""Zyra currency engine: exact FX trust layer.

The Network never custodies funds. Banks and payment
providers move money; Zyra provides exact-decimal rates,
immutable rate history, bridge routing (GTQ->USD->CNY),
Ed25519-signed quotes verifiable offline by any
counterparty, and auditable conversion records.
"""
from __future__ import annotations

from shared_engines.currency.contracts import (
    CurrencyPair,
    Money,
    Quote,
    SignedQuote,
)
from shared_engines.currency.engine import CurrencyEngine
from shared_engines.currency.errors import (
    CurrencyError,
    InvalidRateError,
    NoRouteError,
    QuoteExpiredError,
    RateUnavailableError,
    StaleRateError,
    UnknownCurrencyError,
)
from shared_engines.currency.rates import (
    ProviderChain,
    RateProvider,
    StaticTableRateProvider,
    compose_rates,
)
from shared_engines.currency.registry import CurrencyRegistry
from shared_engines.currency.signing import QuoteSigner
from shared_engines.currency.store import DurableRateStore

__all__ = [
    "CurrencyEngine", "CurrencyError", "CurrencyPair",
    "CurrencyRegistry", "DurableRateStore", "InvalidRateError",
    "Money", "NoRouteError", "ProviderChain", "Quote",
    "QuoteExpiredError", "QuoteSigner", "RateProvider",
    "RateUnavailableError", "SignedQuote", "StaleRateError",
    "StaticTableRateProvider", "UnknownCurrencyError",
    "compose_rates",
]
