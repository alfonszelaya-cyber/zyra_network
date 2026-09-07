from __future__ import annotations

from pathlib import Path

import pytest

from shared_engines.audit.chain import AuditTrail
from shared_engines.common.clocks import FrozenClock
from shared_engines.common.errors import ConfigurationError
from shared_engines.events.contracts import Event, EventCatalog
from shared_engines.events.outbox import Outbox
from shared_engines.identity.contracts import IdentityKind
from shared_engines.identity.engine import IdentityEngine
from shared_engines.identity.errors import IdentityNotFoundError
from shared_engines.observability.backend import InMemoryMetrics
from shared_engines.observability.health import HealthStatus
from shared_engines.storage.database import SQLiteAdapter
from shared_engines.tokenization.engine import TokenEngine
from shared_engines.tokenization.errors import (
    DuplicateRuleError,
    EmissionCapExceededError,
    InsufficientBalanceError,
    ItemInactiveError,
    RuleInactiveError,
    UnknownItemError,
    UnknownRuleError,
)


class _Harness:
    def __init__(self, tmp_path: Path) -> None:
        self.db = SQLiteAdapter(tmp_path / "tokens.db")
        self.clock = FrozenClock()
        self.audit = AuditTrail(self.db, self.clock)
        self.outbox = Outbox(self.db, self.clock)
        self.outbox.ensure_schema()
        self.catalog = EventCatalog()
        for event_type in (
            "token.earned",
            "token.granted",
            "token.redeemed",
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
        self.engine = TokenEngine(
            db=self.db,
            clock=self.clock,
            audit=self.audit,
            outbox=self.outbox,
            catalog=self.catalog,
            identity=self.identity,
            metrics=self.metrics,
        )

    def make_user(self, name: str = "User") -> str:
        user = self.identity.register_identity(
            kind=IdentityKind.PERSON,
            display_name=name,
            actor="registrar",
        )
        return user.zid

    def close(self) -> None:
        self.db.close()


def test_earn_via_rule_mints_and_invariant_holds(
    tmp_path: Path,
) -> None:
    harness = _Harness(tmp_path)
    user = harness.make_user()
    harness.engine.define_rule(
        activity="media.registered", amount=10
    )
    tx = harness.engine.earn(
        subject_zid=user,
        activity="media.registered",
        ref_type="media",
        ref_id="MED-1",
    )
    assert tx.amount == 10
    assert harness.engine.balance(user) == 10
    assert harness.engine.invariant_check()
    assert (
        harness.metrics.counter_value(
            "token.earned", {"activity": "media.registered"}
        )
        == 1
    )
    harness.close()


def test_earn_requires_existing_rule(tmp_path: Path) -> None:
    harness = _Harness(tmp_path)
    user = harness.make_user()
    with pytest.raises(UnknownRuleError):
        harness.engine.earn(
            subject_zid=user,
            activity="never.defined",
            ref_type="x",
            ref_id="y",
        )
    harness.close()


def test_inactive_rule_blocks_earning(tmp_path: Path) -> None:
    harness = _Harness(tmp_path)
    user = harness.make_user()
    harness.engine.define_rule(activity="recycle", amount=5)
    harness.engine.set_rule_active("recycle", active=False)
    with pytest.raises(RuleInactiveError):
        harness.engine.earn(
            subject_zid=user,
            activity="recycle",
            ref_type="event",
            ref_id="r1",
        )
    harness.engine.set_rule_active("recycle", active=True)
    tx = harness.engine.earn(
        subject_zid=user,
        activity="recycle",
        ref_type="event",
        ref_id="r2",
    )
    assert tx.amount == 5
    assert harness.engine.balance(user) == 5
    harness.close()


def test_daily_cap_blocks_then_next_day_allows(
    tmp_path: Path,
) -> None:
    harness = _Harness(tmp_path)
    user = harness.make_user()
    harness.engine.define_rule(
        activity="daily.active",
        amount=1,
        daily_cap=2,
    )
    harness.engine.earn(
        subject_zid=user,
        activity="daily.active",
        ref_type="day",
        ref_id="d1",
    )
    harness.engine.earn(
        subject_zid=user,
        activity="daily.active",
        ref_type="day",
        ref_id="d2",
    )
    with pytest.raises(EmissionCapExceededError):
        harness.engine.earn(
            subject_zid=user,
            activity="daily.active",
            ref_type="day",
            ref_id="d3",
        )
    harness.clock.advance(86_400)
    tx = harness.engine.earn(
        subject_zid=user,
        activity="daily.active",
        ref_type="day",
        ref_id="d4",
    )
    assert tx.amount == 1
    assert harness.engine.balance(user) == 3
    assert harness.engine.invariant_check()
    harness.close()


def test_lifetime_cap_never_resets(tmp_path: Path) -> None:
    harness = _Harness(tmp_path)
    user = harness.make_user()
    harness.engine.define_rule(
        activity="bonus",
        amount=5,
        lifetime_cap=5,
    )
    harness.engine.earn(
        subject_zid=user,
        activity="bonus",
        ref_type="once",
        ref_id="1",
    )
    harness.clock.advance(86_400)
    with pytest.raises(EmissionCapExceededError):
        harness.engine.earn(
            subject_zid=user,
            activity="bonus",
            ref_type="again",
            ref_id="2",
        )
    assert harness.engine.balance(user) == 5
    harness.close()


def test_admin_grant_is_audited_and_evented(
    tmp_path: Path,
) -> None:
    harness = _Harness(tmp_path)
    user = harness.make_user()
    tx = harness.engine.grant(
        subject_zid=user,
        amount=100,
        reason="genesis allocation",
        actor="founder",
    )
    assert tx.kind == "mint"
    assert harness.engine.balance(user) == 100
    assert harness.engine.invariant_check()
    assert harness.audit.verify() >= 1
    events = harness.outbox.pending()
    types = {e.event_type for e in events}
    assert "token.granted" in types
    harness.close()


def test_redeem_burns_balance_atomically(
    tmp_path: Path,
) -> None:
    harness = _Harness(tmp_path)
    user = harness.make_user()
    harness.engine.define_rule(activity="earn.base", amount=50)
    harness.engine.earn(
        subject_zid=user,
        activity="earn.base",
        ref_type="seed",
        ref_id="1",
    )
    harness.engine.define_item(
        item_id="premium_space_1gb",
        title="1 GB premium space",
        cost=30,
    )
    record = harness.engine.redeem(user, "premium_space_1gb")
    assert record.cost == 30
    assert harness.engine.balance(user) == 20
    assert harness.engine.invariant_check()
    listed = harness.engine.list_redemptions(user)
    assert len(listed) == 1
    assert listed[0].item_id == "premium_space_1gb"
    harness.close()


def test_redeem_insufficient_balance_rejected(
    tmp_path: Path,
) -> None:
    harness = _Harness(tmp_path)
    user = harness.make_user()
    harness.engine.define_rule(activity="small", amount=5)
    harness.engine.earn(
        subject_zid=user,
        activity="small",
        ref_type="x",
        ref_id="1",
    )
    harness.engine.define_item(
        item_id="big_item", title="Too expensive", cost=500
    )
    with pytest.raises(InsufficientBalanceError):
        harness.engine.redeem(user, "big_item")
    assert harness.engine.balance(user) == 5
    assert harness.engine.invariant_check()
    harness.close()


def test_item_inactive_and_unknown_cases(
    tmp_path: Path,
) -> None:
    harness = _Harness(tmp_path)
    user = harness.make_user()
    harness.engine.define_rule(activity="base", amount=100)
    harness.engine.earn(
        subject_zid=user,
        activity="base",
        ref_type="x",
        ref_id="1",
    )
    harness.engine.define_item(
        item_id="off_item",
        title="Disabled",
        cost=10,
        active=False,
    )
    with pytest.raises(ItemInactiveError):
        harness.engine.redeem(user, "off_item")
    with pytest.raises(UnknownItemError):
        harness.engine.redeem(user, "never_defined")
    harness.close()


def test_duplicate_rule_activity_rejected(
    tmp_path: Path,
) -> None:
    harness = _Harness(tmp_path)
    harness.engine.define_rule(activity="dup", amount=1)
    with pytest.raises(DuplicateRuleError):
        harness.engine.define_rule(activity="dup", amount=2)
    harness.close()


def test_history_is_complete(tmp_path: Path) -> None:
    harness = _Harness(tmp_path)
    user = harness.make_user()
    harness.engine.define_rule(activity="h", amount=1)
    for index in range(3):
        harness.clock.advance(1)
        harness.engine.earn(
            subject_zid=user,
            activity="h",
            ref_type="seq",
            ref_id=str(index),
        )
    history = harness.engine.history(user)
    assert len(history) == 3
    assert all(tx.kind == "mint" for tx in history)
    harness.close()


def test_invariant_detects_direct_tampering(
    tmp_path: Path,
) -> None:
    harness = _Harness(tmp_path)
    user = harness.make_user()
    harness.engine.define_rule(activity="inv", amount=10)
    harness.engine.earn(
        subject_zid=user,
        activity="inv",
        ref_type="x",
        ref_id="1",
    )
    assert harness.engine.invariant_check()
    harness.db.execute(
        "UPDATE token_accounts SET balance = 999999"
        " WHERE account_id = ?",
        (user,),
    )
    assert not harness.engine.invariant_check()
    assert (
        harness.engine.check_health().status
        is HealthStatus.UNHEALTHY
    )
    harness.close()


def test_unknown_identity_blocked_everywhere(
    tmp_path: Path,
) -> None:
    harness = _Harness(tmp_path)
    harness.engine.define_rule(activity="x", amount=1)
    with pytest.raises(IdentityNotFoundError):
        harness.engine.earn(
            subject_zid="ZID-ghost",
            activity="x",
            ref_type="r",
            ref_id="1",
        )
    with pytest.raises(IdentityNotFoundError):
        harness.engine.balance("ZID-ghost")
    with pytest.raises(IdentityNotFoundError):
        harness.engine.grant(
            subject_zid="ZID-ghost",
            amount=1,
            reason="r",
            actor="admin",
        )
    harness.close()


def test_config_rejects_bad_rule_definitions(
    tmp_path: Path,
) -> None:
    harness = _Harness(tmp_path)
    with pytest.raises(ConfigurationError):
        harness.engine.define_rule(activity="bad", amount=0)
    with pytest.raises(ConfigurationError):
        harness.engine.define_rule(
            activity="bad2", amount=10, daily_cap=5
        )
    with pytest.raises(ConfigurationError):
        harness.engine.define_rule(
            activity="bad3", amount=10, lifetime_cap=5
        )
    harness.close()


def test_outbox_events_cover_full_token_flow(
    tmp_path: Path,
) -> None:
    harness = _Harness(tmp_path)
    user = harness.make_user()
    harness.engine.define_rule(activity="flow", amount=20)
    harness.engine.earn(
        subject_zid=user,
        activity="flow",
        ref_type="x",
        ref_id="1",
    )
    harness.engine.define_item(
        item_id="reward", title="Reward", cost=10
    )
    harness.engine.redeem(user, "reward")
    collected: list[Event] = []

    def collect(event: Event) -> None:
        collected.append(event)

    harness.outbox.dispatch_pending(collect)
    by_type = {event.event_type for event in collected}
    assert by_type >= {"token.earned", "token.redeemed"}
    harness.close()


def test_health_healthy_then_unhealthy_without_storage(
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
