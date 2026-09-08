from __future__ import annotations

from dataclasses import replace
from decimal import Decimal
from pathlib import Path

import pytest

from shared_engines.audit.chain import AuditTrail
from shared_engines.common.clocks import FrozenClock
from shared_engines.common.errors import (
    ConfigurationError,
    IntegrityError,
    NotFoundError,
    ValidationError,
)
from shared_engines.currency.contracts import CurrencyPair, Quote
from shared_engines.currency.engine import CurrencyEngine
from shared_engines.currency.errors import (
    NoRouteError,
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
from shared_engines.currency.signing import QuoteSigner
from shared_engines.currency.store import DurableRateStore
from shared_engines.events.contracts import Event, EventCatalog
from shared_engines.events.outbox import Outbox
from shared_engines.identity.contracts import IdentityKind
from shared_engines.identity.engine import IdentityEngine
from shared_engines.identity.errors import IdentityNotFoundError
from shared_engines.observability.backend import InMemoryMetrics
from shared_engines.observability.health import HealthStatus
from shared_engines.storage.database import SQLiteAdapter
from shared_engines.verification.signatures import Ed25519Signer

RATES = {
    "USD/CNY": "7.25",
    "USD/EUR": "0.92",
    "GTQ/USD": "0.128",
    "USD/MXN": "17.0",
}


class _Dead(RateProvider):
    name = "dead"

    def fetch(self, pair: CurrencyPair, clock: object) -> Quote:
        raise RateUnavailableError("provider down")


class _Harness:
    def __init__(self, tmp_path: Path) -> None:
        self.db = SQLiteAdapter(tmp_path / "fx.db")
        self.clock = FrozenClock()
        self.audit = AuditTrail(self.db, self.clock)
        self.outbox = Outbox(self.db, self.clock)
        self.outbox.ensure_schema()
        self.catalog = EventCatalog()
        for event_type in (
            "currency.quote.issued",
            "currency.conversion.recorded",
            "identity.registered",
            "identity.status_changed",
        ):
            self.catalog.register(event_type)
        self.identity = IdentityEngine(
            db=self.db,
            clock=self.clock,
            audit=self.audit,
            outbox=self.outbox,
            catalog=self.catalog,
        )
        self.metrics = InMemoryMetrics()
        self.signer, _ = Ed25519Signer.generate()
        self.engine = CurrencyEngine(
            db=self.db,
            clock=self.clock,
            providers=[StaticTableRateProvider(RATES, self.clock)],
            signer=self.signer,
            audit=self.audit,
            outbox=self.outbox,
            catalog=self.catalog,
            identity=self.identity,
            metrics=self.metrics,
        )

    def make_user(self, name: str = "Trader") -> str:
        user = self.identity.register_identity(
            kind=IdentityKind.PERSON,
            display_name=name,
            actor="registrar",
        )
        return user.zid

    def dead_engine(self) -> CurrencyEngine:
        """Same store/infra, but the provider is down."""
        return CurrencyEngine(
            db=self.db,
            clock=self.clock,
            providers=[_Dead()],
            signer=self.signer,
            audit=self.audit,
            outbox=self.outbox,
            catalog=self.catalog,
            identity=self.identity,
        )

    def close(self) -> None:
        self.db.close()


def test_decimal_exactness_where_floats_fail() -> None:
    assert Decimal("0.1") + Decimal("0.2") == Decimal("0.3")
    assert compose_rates(
        Decimal("0.128"), Decimal("7.25")
    ) == Decimal("0.928")


def test_quote_direct_pair_exact_and_signed(
    tmp_path: Path,
) -> None:
    harness = _Harness(tmp_path)
    user = harness.make_user()
    signed = harness.engine.quote(
        base="USD", quote_ccy="CNY", requester_zid=user
    )
    assert signed.quote.rate == Decimal("7.25")
    assert QuoteSigner.verify(signed) is True
    forged = replace(signed, issuer_zid="ZID-fake")
    assert QuoteSigner.verify(forged) is False
    harness.close()


def test_bridge_route_gtq_to_cny_via_usd(
    tmp_path: Path,
) -> None:
    harness = _Harness(tmp_path)
    user = harness.make_user()
    signed = harness.engine.quote(
        base="GTQ", quote_ccy="CNY", requester_zid=user
    )
    assert signed.quote.rate == Decimal("0.928")
    assert signed.quote.source.startswith("bridge:USD")
    assert QuoteSigner.verify(signed) is True
    harness.close()


def test_second_quote_served_from_store(tmp_path: Path) -> None:
    harness = _Harness(tmp_path)
    user = harness.make_user()
    first = harness.engine.quote(
        base="USD", quote_ccy="EUR", requester_zid=user
    )
    second = harness.engine.quote(
        base="USD", quote_ccy="EUR", requester_zid=user
    )
    assert second.quote.rate == first.quote.rate
    assert second.quote.quoted_at == first.quote.quoted_at
    harness.close()


def test_stale_only_rate_raises_when_providers_die(
    tmp_path: Path,
) -> None:
    """With live providers the quote refreshes; StaleRateError
    only fires when providers fail AND the stored rate is old.
    """
    harness = _Harness(tmp_path)
    user = harness.make_user()
    harness.engine.quote(
        base="USD", quote_ccy="MXN", requester_zid=user
    )
    harness.clock.advance(301)
    failing = harness.dead_engine()
    with pytest.raises(StaleRateError):
        failing.quote(
            base="USD", quote_ccy="MXN", requester_zid=user
        )
    harness.close()


def test_unknown_currency_and_ghost_requester(
    tmp_path: Path,
) -> None:
    harness = _Harness(tmp_path)
    user = harness.make_user()
    with pytest.raises(UnknownCurrencyError):
        harness.engine.quote(
            base="USD", quote_ccy="ZZZ", requester_zid=user
        )
    with pytest.raises(IdentityNotFoundError):
        harness.engine.quote(
            base="USD", quote_ccy="EUR", requester_zid="ZID-x"
        )
    harness.close()


def test_no_route_when_bridge_leg_missing(
    tmp_path: Path,
) -> None:
    """GTQ and JPY are both registered, but no GTQ/JPY rate
    exists and the USD bridge leg USD/JPY is unavailable:
    honest NoRouteError instead of a guess.
    """
    harness = _Harness(tmp_path)
    user = harness.make_user()
    with pytest.raises(NoRouteError):
        harness.engine.quote(
            base="GTQ", quote_ccy="JPY", requester_zid=user
        )
    harness.close()


def test_convert_records_intent_and_audit(
    tmp_path: Path,
) -> None:
    harness = _Harness(tmp_path)
    user = harness.make_user()
    signed, conversion_id, exact = harness.engine.convert(
        subject_zid=user,
        base="GTQ",
        quote_ccy="USD",
        amount=Decimal("1000.00"),
    )
    assert exact == Decimal("128.0000")
    assert conversion_id.startswith("CNV-")
    record = harness.engine.get_conversion(conversion_id)
    assert record is not None
    assert record["fx_settlement_ref"] is None
    assert harness.audit.verify() >= 1
    assert signed.quote.rate == Decimal("0.128")
    harness.close()


def test_settlement_closes_loop(tmp_path: Path) -> None:
    harness = _Harness(tmp_path)
    user = harness.make_user()
    _, conversion_id, _ = harness.engine.convert(
        subject_zid=user,
        base="USD",
        quote_ccy="MXN",
        amount=Decimal("100"),
    )
    harness.engine.record_settlement(
        conversion_id, settlement_ref="WIRE-12345"
    )
    record = harness.engine.get_conversion(conversion_id)
    assert record is not None
    assert record["fx_settlement_ref"] == "WIRE-12345"
    harness.close()


def test_settlement_unknown_conversion(tmp_path: Path) -> None:
    harness = _Harness(tmp_path)
    with pytest.raises(NotFoundError):
        harness.engine.record_settlement(
            "CNV-missing", settlement_ref="x"
        )
    harness.close()


def test_rate_store_immutable_and_historical(
    tmp_path: Path,
) -> None:
    harness = _Harness(tmp_path)
    provider = StaticTableRateProvider(RATES, harness.clock)
    pair = CurrencyPair("USD", "MXN")
    quote = provider.fetch(pair, harness.clock)
    store = DurableRateStore(harness.db, harness.clock)
    store.save(quote)
    store.save(quote)
    with pytest.raises(IntegrityError):
        store.save(
            Quote(
                pair=pair,
                rate=Decimal("999"),
                quoted_at=quote.quoted_at,
                expires_at=quote.expires_at,
                source="static-table",
            )
        )
    historical = store.as_of(pair, quote.quoted_at + 1)
    assert historical is not None
    assert historical.rate == Decimal("17.0")
    harness.db.close()


def test_outbox_events_from_currency_flow(
    tmp_path: Path,
) -> None:
    harness = _Harness(tmp_path)
    user = harness.make_user()
    harness.engine.convert(
        subject_zid=user,
        base="USD",
        quote_ccy="EUR",
        amount=Decimal("50"),
    )
    collected: list[Event] = []

    def collect(event: Event) -> None:
        collected.append(event)

    harness.outbox.dispatch_pending(collect)
    by_type = {event.event_type for event in collected}
    assert by_type >= {
        "currency.quote.issued",
        "currency.conversion.recorded",
    }
    harness.close()


def test_health_healthy_then_unhealthy(
    tmp_path: Path,
) -> None:
    harness = _Harness(tmp_path)
    assert (
        harness.engine.check_health().status
        is HealthStatus.HEALTHY
    )
    harness.db.close()
    assert (
        harness.engine.check_health().status
        is HealthStatus.UNHEALTHY
    )


def test_provider_chain_and_config_guards() -> None:
    clock = FrozenClock()
    with pytest.raises(RateUnavailableError):
        ProviderChain([_Dead()]).fetch(
            CurrencyPair("USD", "EUR"), clock
        )
    with pytest.raises(ConfigurationError):
        ProviderChain([])
    with pytest.raises(ConfigurationError):
        StaticTableRateProvider({}, clock)
    with pytest.raises(ConfigurationError):
        StaticTableRateProvider({"USD/EUR": "abc"}, clock)


def test_quote_rejects_same_currency(tmp_path: Path) -> None:
    harness = _Harness(tmp_path)
    user = harness.make_user()
    with pytest.raises(ValidationError):
        harness.engine.quote(
            base="USD", quote_ccy="USD", requester_zid=user
        )
    harness.close()
