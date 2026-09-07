from __future__ import annotations

from collections.abc import Mapping
from pathlib import Path

import pytest

from shared_engines.common.clocks import FrozenClock
from shared_engines.common.errors import ValidationError
from shared_engines.events.contracts import Event, EventCatalog
from shared_engines.events.inbox import Inbox
from shared_engines.events.outbox import Outbox
from shared_engines.storage.database import SQLiteAdapter


class SimulatedCrash(Exception):
    """Local failure to prove redelivery semantics."""


def _outbox(adapter: SQLiteAdapter) -> Outbox:
    outbox = Outbox(adapter, FrozenClock())
    outbox.ensure_schema()
    return outbox


def _event(catalog: EventCatalog, clock: FrozenClock) -> Event:
    return catalog.build(
        "test.ping", aggregate_id="agg-1", payload={"n": 1}, clock=clock
    )


def test_outbox_dispatch_marks_published(tmp_path: Path) -> None:
    adapter = SQLiteAdapter(tmp_path / "events.db")
    catalog = EventCatalog()
    catalog.register("test.ping")
    outbox = _outbox(adapter)
    event = _event(catalog, FrozenClock())
    outbox.enqueue(event)
    assert len(outbox.pending()) == 1
    seen: list[str] = []

    def collect(seen_event: Event) -> None:
        seen.append(seen_event.event_id)

    assert outbox.dispatch_pending(collect) == 1
    assert outbox.dispatch_pending(collect) == 0
    assert seen == [event.event_id]
    adapter.close()


def test_outbox_redelivers_on_handler_failure(tmp_path: Path) -> None:
    adapter = SQLiteAdapter(tmp_path / "events.db")
    catalog = EventCatalog()
    catalog.register("test.ping")
    outbox = _outbox(adapter)
    outbox.enqueue(_event(catalog, FrozenClock()))

    def failing(received: Event) -> None:
        raise SimulatedCrash("consumer crashed mid-dispatch")

    with pytest.raises(SimulatedCrash):
        outbox.dispatch_pending(failing)
    assert len(outbox.pending()) == 1
    adapter.close()


def test_inbox_deduplicates_deliveries(tmp_path: Path) -> None:
    adapter = SQLiteAdapter(tmp_path / "events.db")
    clock = FrozenClock()
    catalog = EventCatalog()
    catalog.register("test.ping")
    inbox = Inbox(adapter, clock)
    event = _event(catalog, clock)
    calls: list[int] = []

    def handle(received: Event) -> None:
        calls.append(1)

    assert inbox.process(event, handle) is True
    assert inbox.process(event, handle) is False
    assert calls == [1]
    adapter.close()


def test_inbox_rolls_back_record_and_effect(tmp_path: Path) -> None:
    adapter = SQLiteAdapter(tmp_path / "events.db")
    clock = FrozenClock()
    adapter.execute(
        "CREATE TABLE effects (event_id TEXT NOT NULL,"
        " applied_at REAL NOT NULL)"
    )
    inbox = Inbox(adapter, clock)
    catalog = EventCatalog()
    catalog.register("test.effect")
    event = catalog.build(
        "test.effect", aggregate_id="agg", payload={}, clock=clock
    )

    def failing_effect(received: Event) -> None:
        adapter.execute(
            "INSERT INTO effects (event_id, applied_at) VALUES (?, ?)",
            (received.event_id, clock.now()),
        )
        raise SimulatedCrash("effect crashed")

    with pytest.raises(SimulatedCrash):
        inbox.process(event, failing_effect)
    row = adapter.query_one("SELECT COUNT(*) AS n FROM effects")
    assert row is not None
    assert int(row["n"]) == 0
    assert inbox.process(event, lambda e: None) is True
    adapter.close()


def test_catalog_rejects_and_fingerprints_stable() -> None:
    catalog = EventCatalog()
    clock = FrozenClock()
    with pytest.raises(ValidationError):
        _event(catalog, clock)
    catalog.register("test.ping")
    first = _event(catalog, clock)
    second = _event(catalog, clock)
    assert first.fingerprint == second.fingerprint
    assert first.event_id != second.event_id
    assert "test.ping" in catalog.registered_types


def test_catalog_versions_are_selectable() -> None:
    catalog = EventCatalog()
    clock = FrozenClock()

    def v1_validator(payload: Mapping[str, object]) -> None:
        if "v1_field" not in payload:
            raise ValidationError("v1 requires v1_field")

    def v2_validator(payload: Mapping[str, object]) -> None:
        if "v2_field" not in payload:
            raise ValidationError("v2 requires v2_field")

    catalog.register("test.v", schema_version=1, validator=v1_validator)
    catalog.register("test.v", schema_version=2, validator=v2_validator)
    event_v2 = catalog.build(
        "test.v",
        aggregate_id="a",
        payload={"v2_field": 1},
        clock=clock,
    )
    assert event_v2.schema_version == 2
    event_v1 = catalog.build(
        "test.v",
        aggregate_id="a",
        payload={"v1_field": 1},
        clock=clock,
        schema_version=1,
    )
    assert event_v1.schema_version == 1
    with pytest.raises(ValidationError):
        catalog.build(
            "test.v",
            aggregate_id="a",
            payload={"v2_field": 1},
            clock=clock,
            schema_version=1,
        )
