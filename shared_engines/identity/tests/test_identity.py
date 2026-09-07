from __future__ import annotations

import sqlite3
from pathlib import Path

import pytest

from shared_engines.audit.chain import AuditTrail
from shared_engines.common.clocks import FrozenClock
from shared_engines.events.contracts import Event, EventCatalog
from shared_engines.events.outbox import Outbox
from shared_engines.identity.contracts import (
    Identity,
    IdentityKind,
    IdentityStatus,
    VALID_TRANSITIONS,
)
from shared_engines.identity.engine import IdentityEngine
from shared_engines.identity.errors import (
    IdentityNotFoundError,
    InvalidTransitionError,
)
from shared_engines.observability.health import HealthStatus
from shared_engines.storage.database import SQLiteAdapter


class _Harness:
    def __init__(self, tmp_path: Path) -> None:
        self.db = SQLiteAdapter(tmp_path / "identity.db")
        self.clock = FrozenClock()
        self.audit = AuditTrail(self.db, self.clock)
        self.outbox = Outbox(self.db, self.clock)
        self.outbox.ensure_schema()
        self.catalog = EventCatalog()
        self.catalog.register("identity.registered")
        self.catalog.register("identity.status_changed")
        self.engine = IdentityEngine(
            db=self.db,
            clock=self.clock,
            audit=self.audit,
            outbox=self.outbox,
            catalog=self.catalog,
        )

    def close(self) -> None:
        self.db.close()


def _register(harness: _Harness, name: str = "Ada") -> Identity:
    return harness.engine.register_identity(
        kind=IdentityKind.PERSON,
        display_name=name,
        actor="registrar-1",
    )


def test_register_creates_unique_zid_in_registered_state(
    tmp_path: Path,
) -> None:
    harness = _Harness(tmp_path)
    identity = _register(harness)
    assert identity.zid.startswith("ZID-")
    assert identity.status is IdentityStatus.REGISTERED
    assert identity.kind is IdentityKind.PERSON
    assert identity.display_name == "Ada"
    second = _register(harness, "Bob")
    assert second.zid != identity.zid
    harness.close()


def test_register_is_audited_and_emits_event(tmp_path: Path) -> None:
    harness = _Harness(tmp_path)
    identity = _register(harness)
    assert harness.audit.verify() == 1
    events = harness.outbox.pending()
    assert len(events) == 1
    assert events[0].event_type == "identity.registered"
    assert events[0].aggregate_id == identity.zid
    harness.close()


def test_happy_lifecycle_path(tmp_path: Path) -> None:
    harness = _Harness(tmp_path)
    identity = _register(harness)
    moved = harness.engine.transition_identity(
        identity.zid,
        IdentityStatus.ACTIVE,
        actor="admin",
        reason="verified offline",
    )
    assert moved.status is IdentityStatus.ACTIVE
    moved = harness.engine.transition_identity(
        moved.zid,
        IdentityStatus.SUSPENDED,
        actor="admin",
        reason="under review",
    )
    assert moved.status is IdentityStatus.SUSPENDED
    moved = harness.engine.transition_identity(
        moved.zid,
        IdentityStatus.ACTIVE,
        actor="admin",
        reason="cleared",
    )
    assert moved.status is IdentityStatus.ACTIVE
    assert harness.audit.verify() == 4
    harness.close()


def test_invalid_transitions_are_blocked(tmp_path: Path) -> None:
    harness = _Harness(tmp_path)
    identity = _register(harness)
    with pytest.raises(InvalidTransitionError):
        harness.engine.transition_identity(
            identity.zid,
            IdentityStatus.VERIFIED,
            actor="admin",
            reason="skip verification",
        )
    with pytest.raises(InvalidTransitionError):
        harness.engine.transition_identity(
            identity.zid,
            IdentityStatus.SUSPENDED,
            actor="admin",
            reason="not active yet",
        )
    entry = harness.engine.require_identity(identity.zid)
    assert entry.status is IdentityStatus.REGISTERED
    harness.close()


def test_revocation_is_terminal(tmp_path: Path) -> None:
    harness = _Harness(tmp_path)
    identity = _register(harness)
    revoked = harness.engine.transition_identity(
        identity.zid,
        IdentityStatus.REVOKED,
        actor="admin",
        reason="fraud",
    )
    assert revoked.status is IdentityStatus.REVOKED
    with pytest.raises(InvalidTransitionError):
        harness.engine.transition_identity(
            revoked.zid,
            IdentityStatus.ACTIVE,
            actor="admin",
            reason="resurrect",
        )
    harness.close()


def test_unknown_zid_raises_typed_error(tmp_path: Path) -> None:
    harness = _Harness(tmp_path)
    with pytest.raises(IdentityNotFoundError):
        harness.engine.require_identity("ZID-missing")
    with pytest.raises(IdentityNotFoundError):
        harness.engine.transition_identity(
            "ZID-missing",
            IdentityStatus.ACTIVE,
            actor="admin",
            reason="ghost",
        )
    harness.close()


def test_list_by_status_pagination(tmp_path: Path) -> None:
    harness = _Harness(tmp_path)
    for index in range(5):
        _register(harness, f"User{index}")
    page1 = harness.engine.list_by_status(
        IdentityStatus.REGISTERED, offset=0, limit=3
    )
    assert page1.total == 5
    assert len(page1.items) == 3
    assert page1.has_more
    page2 = harness.engine.list_by_status(
        IdentityStatus.REGISTERED, offset=3, limit=3
    )
    assert len(page2.items) == 2
    assert not page2.has_more
    harness.close()


def test_duplicate_zid_is_rejected_by_database(
    tmp_path: Path,
) -> None:
    harness = _Harness(tmp_path)
    identity = _register(harness)
    with pytest.raises(sqlite3.IntegrityError):
        with harness.db.transaction() as cursor:
            cursor.execute(
                "INSERT INTO identities"
                " (zid, kind, status, display_name,"
                "  created_at, updated_at, contract_version)"
                " VALUES (?, ?, ?, ?, ?, ?, ?)",
                (
                    identity.zid,
                    "person",
                    "REGISTERED",
                    "clone",
                    1.0,
                    1.0,
                    1,
                ),
            )
    harness.close()


def test_transitions_table_covers_all_states() -> None:
    for status in IdentityStatus:
        assert status in VALID_TRANSITIONS
    assert VALID_TRANSITIONS[IdentityStatus.REVOKED] == frozenset()
    assert IdentityStatus.ACTIVE in (
        VALID_TRANSITIONS[IdentityStatus.REGISTERED]
    )


def test_outbox_events_carry_transition_payloads(
    tmp_path: Path,
) -> None:
    harness = _Harness(tmp_path)
    identity = _register(harness)
    harness.engine.transition_identity(
        identity.zid,
        IdentityStatus.ACTIVE,
        actor="admin",
        reason="go live",
    )
    collected: list[Event] = []

    def collect(event: Event) -> None:
        collected.append(event)

    harness.outbox.dispatch_pending(collect)
    assert len(collected) == 2
    by_type = {event.event_type: event for event in collected}
    assert "identity.registered" in by_type
    assert "identity.status_changed" in by_type
    changed = by_type["identity.status_changed"]
    assert changed.aggregate_id == identity.zid
    assert changed.payload["from"] == "REGISTERED"
    assert changed.payload["to"] == "ACTIVE"
    assert changed.payload["reason"] == "go live"
    harness.close()


def test_identity_health_reflects_storage(tmp_path: Path) -> None:
    harness = _Harness(tmp_path)
    assert harness.engine.check_health().status is HealthStatus.HEALTHY
    harness.db.close()
    assert (
        harness.engine.check_health().status
        is HealthStatus.UNHEALTHY
    )
