"""Rate providers behind a protocol + exact composition.

The domain depends on ``RateProvider`` only. The static
table is an operator-maintained reference source that
validates every entry at construction.
"""
from __future__ import annotations

from collections.abc import Sequence
from decimal import Decimal

from shared_engines.common.clocks import Clock
from shared_engines.common.errors import ConfigurationError
from shared_engines.currency.contracts import CurrencyPair, Quote
from shared_engines.currency.errors import RateUnavailableError


class RateProvider:
    """A named source of point-in-time quotes."""

    name: str

    def fetch(self, pair: CurrencyPair, clock: Clock) -> Quote:
        raise RateUnavailableError(
            "RateProvider.fetch must be implemented"
        )


class StaticTableRateProvider(RateProvider):
    """Operator-maintained reference rates (exact decimals)."""

    def __init__(
        self,
        rates: dict[str, str],
        clock: Clock,
        *,
        ttl_seconds: float = 300.0,
    ) -> None:
        if not rates:
            raise ConfigurationError(
                "static rate table must not be empty"
            )
        self._clock = clock
        self._rates: dict[str, Decimal] = {}
        self.name = "static-table"
        self._ttl = ttl_seconds
        for key, raw in rates.items():
            try:
                value = Decimal(raw)
            except Exception as exc:
                raise ConfigurationError(
                    f"static rate {key} is not a decimal"
                ) from exc
            if not value.is_finite() or value <= 0:
                raise ConfigurationError(
                    f"static rate {key} must be positive"
                )
            self._rates[key] = value

    def fetch(self, pair: CurrencyPair, clock: Clock) -> Quote:
        rate = self._rates.get(pair.normalized)
        if rate is None:
            raise RateUnavailableError(
                f"no quote for {pair.normalized}"
            )
        now = clock.now()
        return Quote(
            pair=pair,
            rate=rate,
            quoted_at=now,
            expires_at=now + self._ttl,
            source=self.name,
        )


class ProviderChain:
    """Tries providers in order; first success wins."""

    def __init__(self, providers: Sequence[RateProvider]) -> None:
        if not providers:
            raise ConfigurationError(
                "at least one provider required"
            )
        self._providers: tuple[RateProvider, ...] = tuple(providers)

    def fetch(self, pair: CurrencyPair, clock: Clock) -> Quote:
        failures: list[str] = []
        for provider in self._providers:
            try:
                return provider.fetch(pair, clock)
            except RateUnavailableError as exc:
                failures.append(f"{provider.name}: {exc}")
        raise RateUnavailableError(
            f"all providers exhausted: {'; '.join(failures)}"
        )


def compose_rates(leg1: Decimal, leg2: Decimal) -> Decimal:
    """Composes two legs multiplicatively (exact)."""
    return leg1 * leg2
