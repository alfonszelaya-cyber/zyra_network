"""Currency engine: quotes, bridge routing, signed FX records.

Bridge logic lives inside the engine: direct quote first,
then via the configured bridge currency. Stale stored rates
are refused, never used silently. Settlement happens
outside the Network (banks/providers move the funds); its
reference attaches via record_settlement() - never faked.
"""
from __future__ import annotations

from decimal import Decimal

from shared_engines.audit.chain import AuditTrail
from shared_engines.common.clocks import Clock
from shared_engines.common.errors import (
    NotFoundError,
    ValidationError,
)
from shared_engines.common.identifiers import new_id
from shared_engines.common.validation import (
    require_non_empty_str,
    require_positive_number,
)
from shared_engines.currency.contracts import (
    CurrencyPair,
    Quote,
    SignedQuote,
)
from shared_engines.currency.errors import (
    NoRouteError,
    QuoteExpiredError,
    RateUnavailableError,
    StaleRateError,
)
from shared_engines.currency.rates import (
    ProviderChain,
    RateProvider,
    compose_rates,
)
from shared_engines.currency.registry import CurrencyRegistry
from shared_engines.currency.signing import QuoteSigner
from shared_engines.currency.store import DurableRateStore
from shared_engines.events.contracts import EventCatalog
from shared_engines.events.outbox import Outbox
from shared_engines.identity.engine import IdentityEngine
from shared_engines.observability.backend import (
    MetricsBackend,
    NoopMetrics,
    engine_logger,
)
from shared_engines.observability.health import (
    ComponentHealth,
    HealthStatus,
)
from shared_engines.storage.database import Database
from shared_engines.storage.migrations import (
    Migration,
    MigrationRunner,
)
from shared_engines.verification.signatures import Ed25519Signer

EVENT_QUOTED = "currency.quote.issued"
EVENT_CONVERTED = "currency.conversion.recorded"

CONVERSIONS_MIGRATIONS = (
    Migration(
        1,
        "conversions",
        (
            "CREATE TABLE conversions ("
            " conversion_id TEXT PRIMARY KEY,"
            " subject_zid TEXT NOT NULL,"
            " base TEXT NOT NULL,"
            " quote_ccy TEXT NOT NULL,"
            " base_amount TEXT NOT NULL,"
            " quote_amount TEXT NOT NULL,"
            " rate TEXT NOT NULL,"
            " quote_source TEXT NOT NULL,"
            " fx_settlement_ref TEXT,"
            " created_at REAL NOT NULL,"
            " contract_version INTEGER NOT NULL)",
            "CREATE INDEX conversions_subject"
            " ON conversions (subject_zid, created_at)",
        ),
    ),
)


class CurrencyEngine:
    def __init__(
        self,
        *,
        db: Database,
        clock: Clock,
        providers: list[RateProvider],
        signer: Ed25519Signer,
        audit: AuditTrail,
        outbox: Outbox,
        catalog: EventCatalog,
        identity: IdentityEngine,
        bridge: str = "USD",
        max_rate_age_seconds: float = 300.0,
        metrics: MetricsBackend | None = None,
    ) -> None:
        require_non_empty_str(bridge, "bridge", config=True)
        require_positive_number(
            max_rate_age_seconds,
            "max_rate_age_seconds",
            config=True,
        )
        self._bridge = bridge.upper()
        self._max_age = max_rate_age_seconds
        self._registry = CurrencyRegistry()
        self._chain = ProviderChain(list(providers))
        self._store = DurableRateStore(db, clock)
        self._quote_signer = QuoteSigner(signer)
        self._identity = identity
        self._audit = audit
        self._outbox = outbox
        self._clock = clock
        self._db = db
        self._catalog = catalog
        self._metrics = metrics if metrics is not None else NoopMetrics()
        self._log = engine_logger("currency")
        self._catalog.register(EVENT_QUOTED)
        self._catalog.register(EVENT_CONVERTED)
        MigrationRunner(
            db, "currency.conversions", CONVERSIONS_MIGRATIONS
        ).run(clock)

    @property
    def registry(self) -> CurrencyRegistry:
        return self._registry

    def quote(
        self,
        *,
        base: str,
        quote_ccy: str,
        requester_zid: str,
    ) -> SignedQuote:
        self._identity.require_identity(requester_zid)
        base_u = base.upper().strip()
        quote_u = quote_ccy.upper().strip()
        self._registry.require(base_u)
        self._registry.require(quote_u)
        pair = CurrencyPair(base_u, quote_u)
        stored = self._store.latest(pair)
        now = self._clock.now()
        if stored is not None and (
            now - stored.quoted_at
        ) <= self._max_age:
            quote = stored
        else:
            quote = self._fetch_quote(pair, stored)
            self._store.save(quote)
        signed = self._quote_signer.sign(
            quote, issuer_zid=requester_zid
        )
        event = self._catalog.build(
            EVENT_QUOTED,
            aggregate_id=pair.normalized,
            payload={
                "pair": pair.normalized,
                "rate": str(quote.rate),
                "source": quote.source,
                "requester_zid": requester_zid,
            },
            clock=self._clock,
        )
        self._outbox.enqueue(event)
        self._metrics.increment(
            "currency.quoted", tags={"pair": pair.normalized}
        )
        self._log.info(
            "quoted pair=%s rate=%s", pair.normalized, quote.rate
        )
        return signed

    def convert(
        self,
        *,
        subject_zid: str,
        base: str,
        quote_ccy: str,
        amount: Decimal,
    ) -> tuple[SignedQuote, str, Decimal]:
        """Quotes, checks freshness, records the intent."""
        self._identity.require_identity(subject_zid)
        if not isinstance(amount, Decimal):
            raise ValidationError(
                "amount must be Decimal (build from str)"
            )
        if not amount.is_finite() or amount <= 0:
            raise ValidationError(
                "amount must be positive and finite"
            )
        signed = self.quote(
            base=base,
            quote_ccy=quote_ccy,
            requester_zid=subject_zid,
        )
        quote = signed.quote
        if self._clock.now() > quote.expires_at:
            raise QuoteExpiredError(
                "quote expired before conversion"
            )
        exact = amount * quote.rate
        conversion_id = f"CNV-{new_id()}"
        with self._db.transaction() as cursor:
            cursor.execute(
                "INSERT INTO conversions"
                " (conversion_id, subject_zid, base, quote_ccy,"
                "  base_amount, quote_amount, rate, quote_source,"
                "  fx_settlement_ref, created_at,"
                "  contract_version)"
                " VALUES (?, ?, ?, ?, ?, ?, ?, ?, NULL, ?, ?)",
                (
                    conversion_id,
                    subject_zid,
                    base.upper(),
                    quote_ccy.upper(),
                    str(amount),
                    str(exact),
                    str(quote.rate),
                    quote.source,
                    self._clock.now(),
                    1,
                ),
            )
        event = self._catalog.build(
            EVENT_CONVERTED,
            aggregate_id=conversion_id,
            payload={
                "conversion_id": conversion_id,
                "subject_zid": subject_zid,
                "pair": quote.pair.normalized,
                "rate": str(quote.rate),
            },
            clock=self._clock,
        )
        self._outbox.enqueue(event)
        self._audit.append(
            event_type=EVENT_CONVERTED,
            actor=subject_zid,
            subject=conversion_id,
            payload={
                "pair": quote.pair.normalized,
                "rate": str(quote.rate),
                "base_amount": str(amount),
                "quote_amount": str(exact),
            },
        )
        self._metrics.increment("currency.converted")
        self._log.info(
            "converted id=%s pair=%s",
            conversion_id,
            quote.pair.normalized,
        )
        return signed, conversion_id, exact

    def record_settlement(
        self, conversion_id: str, *, settlement_ref: str
    ) -> None:
        """Attaches the external provider's settlement ref."""
        require_non_empty_str(settlement_ref, "settlement_ref")
        row = self._db.query_one(
            "SELECT conversion_id FROM conversions"
            " WHERE conversion_id = ?",
            (conversion_id,),
        )
        if row is None:
            raise NotFoundError(
                f"unknown conversion: {conversion_id}"
            )
        self._db.execute(
            "UPDATE conversions SET fx_settlement_ref = ?"
            " WHERE conversion_id = ?",
            (settlement_ref, conversion_id),
        )
        self._audit.append(
            event_type="currency.conversion.settled",
            actor="fx-settlement",
            subject=conversion_id,
            payload={"settlement_ref": settlement_ref},
        )
        self._log.info("settled conversion=%s", conversion_id)

    def get_conversion(
        self, conversion_id: str
    ) -> dict[str, object] | None:
        row = self._db.query_one(
            "SELECT * FROM conversions WHERE conversion_id = ?",
            (conversion_id,),
        )
        if row is None:
            return None
        settlement = row["fx_settlement_ref"]
        return {
            "conversion_id": str(row["conversion_id"]),
            "subject_zid": str(row["subject_zid"]),
            "base": str(row["base"]),
            "quote": str(row["quote_ccy"]),
            "base_amount": str(row["base_amount"]),
            "quote_amount": str(row["quote_amount"]),
            "rate": str(row["rate"]),
            "quote_source": str(row["quote_source"]),
            "fx_settlement_ref": (
                None if settlement is None else str(settlement)
            ),
            "created_at": float(row["created_at"]),
        }

    def check_health(self) -> ComponentHealth:
        if not self._db.ping():
            return ComponentHealth(
                "currency",
                HealthStatus.UNHEALTHY,
                "storage unavailable",
            )
        return ComponentHealth(
            "currency",
            HealthStatus.HEALTHY,
            "rates + conversions ok",
        )

    def _fetch_quote(
        self, pair: CurrencyPair, stored: Quote | None
    ) -> Quote:
        """Direct first; via bridge otherwise. Honest failures."""
        try:
            return self._chain.fetch(pair, self._clock)
        except RateUnavailableError:
            pass
        if (
            pair.base == self._bridge
            or pair.quote == self._bridge
        ):
            if stored is not None:
                raise StaleRateError(
                    f"only stored rate for"
                    f" {pair.normalized} is stale"
                ) from None
            raise
        try:
            leg_in = self._chain.fetch(
                CurrencyPair(pair.base, self._bridge),
                self._clock,
            )
            leg_out = self._chain.fetch(
                CurrencyPair(self._bridge, pair.quote),
                self._clock,
            )
        except RateUnavailableError:
            if stored is not None:
                raise StaleRateError(
                    f"only stored rate for"
                    f" {pair.normalized} is stale"
                ) from None
            raise NoRouteError(
                f"no route for {pair.normalized}"
            ) from None
        ttl = min(
            leg_in.expires_at - leg_in.quoted_at,
            leg_out.expires_at - leg_out.quoted_at,
        )
        now = self._clock.now()
        return Quote(
            pair=pair,
            rate=compose_rates(leg_in.rate, leg_out.rate),
            quoted_at=now,
            expires_at=now + ttl,
            source=f"bridge:{self._bridge}",
        )
