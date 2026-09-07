"""Token engine: the public facade of the capability.

Earn is the only user-facing minting path and it always goes
through a rule bound to a real Network activity reference.
Grants are admin-only and audited. Redemptions burn tokens
against catalog items (tangible value). Every movement is
evented through the outbox and audited in the hash chain.
"""
from __future__ import annotations

from shared_engines.audit.chain import AuditTrail
from shared_engines.common.clocks import Clock
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
from shared_engines.tokenization.errors import UnknownRuleError
from shared_engines.tokenization.ledger import (
    EmissionRule,
    LedgerTransaction,
    RedemptionItem,
    RedemptionRecord,
    TokenLedger,
)

EVENT_TOKEN_EARNED = "token.earned"
EVENT_TOKEN_GRANTED = "token.granted"
EVENT_TOKEN_REDEEMED = "token.redeemed"
TOKEN_EVENT_TYPES = (
    EVENT_TOKEN_EARNED,
    EVENT_TOKEN_GRANTED,
    EVENT_TOKEN_REDEEMED,
)


class TokenEngine:
    def __init__(
        self,
        *,
        db: Database,
        clock: Clock,
        audit: AuditTrail,
        outbox: Outbox,
        catalog: EventCatalog,
        identity: IdentityEngine,
        metrics: MetricsBackend | None = None,
    ) -> None:
        self._db = db
        self._clock = clock
        self._audit = audit
        self._outbox = outbox
        self._catalog = catalog
        self._identity = identity
        self._metrics = metrics if metrics is not None else NoopMetrics()
        self._log = engine_logger("tokenization")
        for event_type in TOKEN_EVENT_TYPES:
            self._catalog.register(event_type)
        self._ledger = TokenLedger(db, clock)

    @property
    def ledger(self) -> TokenLedger:
        return self._ledger

    def define_rule(
        self,
        *,
        activity: str,
        amount: int,
        daily_cap: int | None = None,
        lifetime_cap: int | None = None,
    ) -> EmissionRule:
        rule = self._ledger.define_rule(
            activity=activity,
            amount=amount,
            daily_cap=daily_cap,
            lifetime_cap=lifetime_cap,
        )
        self._log.info(
            "rule defined activity=%s amount=%d",
            activity,
            amount,
        )
        return rule

    def set_rule_active(
        self, activity: str, *, active: bool
    ) -> EmissionRule:
        return self._ledger.set_rule_active(
            activity, active=active
        )

    def list_rules(self) -> tuple[EmissionRule, ...]:
        return self._ledger.list_rules()

    def earn(
        self,
        *,
        subject_zid: str,
        activity: str,
        ref_type: str,
        ref_id: str,
    ) -> LedgerTransaction:
        self._identity.require_identity(subject_zid)
        tx = self._ledger.earn(
            subject_zid=subject_zid,
            activity=activity,
            ref_type=ref_type,
            ref_id=ref_id,
        )
        event = self._catalog.build(
            EVENT_TOKEN_EARNED,
            aggregate_id=subject_zid,
            payload={
                "subject_zid": subject_zid,
                "activity": activity,
                "amount": tx.amount,
                "ref_type": ref_type,
                "ref_id": ref_id,
                "tx_id": tx.tx_id,
            },
            clock=self._clock,
        )
        self._outbox.enqueue(event)
        self._audit.append(
            event_type=EVENT_TOKEN_EARNED,
            actor=subject_zid,
            subject=tx.tx_id,
            payload={
                "activity": activity,
                "amount": tx.amount,
                "ref_type": ref_type,
                "ref_id": ref_id,
            },
        )
        self._metrics.increment(
            "token.earned", tags={"activity": activity}
        )
        self._log.info(
            "earned subject=%s activity=%s amount=%d",
            subject_zid,
            activity,
            tx.amount,
        )
        return tx

    def grant(
        self,
        *,
        subject_zid: str,
        amount: int,
        reason: str,
        actor: str,
    ) -> LedgerTransaction:
        self._identity.require_identity(subject_zid)
        tx = self._ledger.grant(
            subject_zid=subject_zid,
            amount=amount,
            reason=reason,
            actor=actor,
        )
        event = self._catalog.build(
            EVENT_TOKEN_GRANTED,
            aggregate_id=subject_zid,
            payload={
                "subject_zid": subject_zid,
                "amount": amount,
                "reason": reason,
                "actor": actor,
                "tx_id": tx.tx_id,
            },
            clock=self._clock,
        )
        self._outbox.enqueue(event)
        self._audit.append(
            event_type=EVENT_TOKEN_GRANTED,
            actor=actor,
            subject=tx.tx_id,
            payload={
                "subject_zid": subject_zid,
                "amount": amount,
                "reason": reason,
            },
        )
        self._metrics.increment("token.granted")
        self._log.info(
            "granted subject=%s amount=%d by=%s",
            subject_zid,
            amount,
            actor,
        )
        return tx

    def balance(self, subject_zid: str) -> int:
        self._identity.require_identity(subject_zid)
        return self._ledger.balance(subject_zid)

    def history(
        self, subject_zid: str, *, limit: int = 50
    ) -> tuple[LedgerTransaction, ...]:
        self._identity.require_identity(subject_zid)
        return self._ledger.history(subject_zid, limit=limit)

    def define_item(
        self,
        *,
        item_id: str,
        title: str,
        cost: int,
        active: bool = True,
    ) -> RedemptionItem:
        item = self._ledger.define_item(
            item_id=item_id,
            title=title,
            cost=cost,
            active=active,
        )
        self._log.info(
            "item defined item=%s cost=%d", item_id, cost
        )
        return item

    def list_items(self) -> tuple[RedemptionItem, ...]:
        return self._ledger.list_items()

    def redeem(
        self, subject_zid: str, item_id: str
    ) -> RedemptionRecord:
        self._identity.require_identity(subject_zid)
        record = self._ledger.redeem(subject_zid, item_id)
        event = self._catalog.build(
            EVENT_TOKEN_REDEEMED,
            aggregate_id=subject_zid,
            payload={
                "subject_zid": subject_zid,
                "item_id": item_id,
                "cost": record.cost,
                "redemption_id": record.redemption_id,
            },
            clock=self._clock,
        )
        self._outbox.enqueue(event)
        self._audit.append(
            event_type=EVENT_TOKEN_REDEEMED,
            actor=subject_zid,
            subject=record.redemption_id,
            payload={
                "item_id": item_id,
                "cost": record.cost,
            },
        )
        self._metrics.increment("token.redeemed")
        self._log.info(
            "redeemed subject=%s item=%s cost=%d",
            subject_zid,
            item_id,
            record.cost,
        )
        return record

    def list_redemptions(
        self, subject_zid: str
    ) -> tuple[RedemptionRecord, ...]:
        self._identity.require_identity(subject_zid)
        return self._ledger.list_redemptions(subject_zid)

    def invariant_check(self) -> bool:
        return self._ledger.invariant_check()

    def require_rule(self, activity: str) -> EmissionRule:
        rule = self._ledger.get_rule_by_activity(activity)
        if rule is None:
            raise UnknownRuleError(
                f"unknown rule activity: {activity}"
            )
        return rule

    def check_health(self) -> ComponentHealth:
        if not self._db.ping():
            return ComponentHealth(
                "tokenization",
                HealthStatus.UNHEALTHY,
                "storage unavailable",
            )
        if not self._ledger.invariant_check():
            return ComponentHealth(
                "tokenization",
                HealthStatus.UNHEALTHY,
                "accounting invariant broken",
            )
        return ComponentHealth(
            "tokenization",
            HealthStatus.HEALTHY,
            "ledger invariant holds",
        )
