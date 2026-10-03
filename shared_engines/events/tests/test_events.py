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


def test_bridge_deliver_once_and_dedup(
    tmp_path,
) -> None:
    """AX-BRIDGE: la Red reparte ->
    NEXO recibe UNA vez; simulacion
    de crash (evento vuelve a
    PENDING) -> re-relay NO duplica
    efecto (Inbox dedup)."""
    from shared_engines.events.outbox import (
        Outbox, InterAppBridge)
    from shared_engines.events.inbox import (
        Inbox)
    from shared_engines.events.contracts import (
        EventCatalog)
    from shared_engines.storage.database import (
        SQLiteAdapter)
    from shared_engines.common.clocks import (
        FrozenClock)
    cat = EventCatalog()
    cat.register(
        "agro.sale.created")
    db_red = SQLiteAdapter(
        tmp_path / "red.db")
    db_nexo = SQLiteAdapter(
        tmp_path / "nexo.db")
    clock = FrozenClock()
    out_red = Outbox(db_red, clock)
    out_red.ensure_schema()
    ev = cat.build(
        "agro.sale.created",
        aggregate_id="S1",
        payload={"total": 100},
        clock=clock)
    out_red.enqueue(ev)
    inbox_nexo = Inbox(
        db_nexo, clock)
    recibidos = []
    bridge = InterAppBridge(
        db=db_red, clock=clock,
        source=out_red)
    bridge.subscribe(
        app_id="nexo",
        event_types=(
            "agro.sale"
            ".created",),
        inbox=inbox_nexo,
        handler=(
            recibidos.append))
    r1 = bridge.relay()
    assert r1["drained"] == 1, str(r1)
    assert r1["delivered"] == 1, str(r1)
    assert len(recibidos) == 1
    db_red.execute(
        "UPDATE events_outbox SET"
        " state = 'PENDING',"
        " published_at = NULL"
        " WHERE event_id = ?",
        (ev.event_id,))
    r2 = bridge.relay()
    assert r2["drained"] == 1
    assert (r2["delivered"]
            == 0), str(r2)
    assert r2["duplicates"] == 1, str(r2)
    assert len(recibidos) == 1, (
        "dedup fallo")
    assert (bridge.subscriptions(
        app_id="nexo")
        == ("agro.sale"
            ".created",))


def test_bridge_routes_by_type(
    tmp_path,
) -> None:
    """AX-BRIDGE: cada evento llega
    solo a quien se suscribio a su
    tipo (fuente unica por dominio);
    no suscrito NO recibe."""
    from shared_engines.events.outbox import (
        Outbox, InterAppBridge)
    from shared_engines.events.inbox import (
        Inbox)
    from shared_engines.events.contracts import (
        EventCatalog)
    from shared_engines.storage.database import (
        SQLiteAdapter)
    from shared_engines.common.clocks import (
        FrozenClock)
    cat = EventCatalog()
    cat.register(
        "life.birth.registered")
    cat.register(
        "agro.sale.created")
    db_s = SQLiteAdapter(
        tmp_path / "s.db")
    db_r = SQLiteAdapter(
        tmp_path / "r.db")
    clock = FrozenClock()
    out_s = Outbox(db_s, clock)
    out_r = Outbox(db_r, clock)
    out_s.ensure_schema()
    out_r.ensure_schema()
    e1 = cat.build(
        "life.birth.registered",
        aggregate_id="P1",
        payload={}, clock=clock)
    e2 = cat.build(
        "agro.sale.created",
        aggregate_id="S2",
        payload={}, clock=clock)
    out_s.enqueue(e1)
    out_s.enqueue(e2)
    out_r.enqueue(e1)
    out_r.enqueue(e2)
    got_axis = []
    got_nexo = []
    bridge = InterAppBridge(
        db=db_r, clock=clock,
        source=out_r)
    bridge.subscribe(
        app_id="axis",
        event_types=(
            "life.birth"
            ".registered",),
        inbox=Inbox(
            SQLiteAdapter(
                tmp_path
                / "ax.db"),
            clock),
        handler=(
            got_axis.append))
    bridge.subscribe(
        app_id="nexo",
        event_types=(
            "agro.sale"
            ".created",),
        inbox=Inbox(
            SQLiteAdapter(
                tmp_path
                / "nx.db"),
            clock),
        handler=(
            got_nexo.append))
    bridge.relay()
    assert len(got_axis) == 1
    assert (got_axis[0]
            .event_type
            == "life.birth"
            ".registered")
    assert len(got_nexo) == 1
    assert (got_nexo[0]
            .event_type
            == "agro.sale"
            ".created")


def test_relay_forever_autonomous(
    tmp_path,
) -> None:
    """RED-RELAY: el cartero
    distribuye solo: evento
    encolado DESPUES de arrancar
    el bucle es entregado sin
    llamada manual; stop termina
    limpio. Todas las esperas con
    timeout: el test no puede
    colgar."""
    import threading
    from shared_engines.events.outbox import (
        Outbox, InterAppBridge)
    from shared_engines.events.inbox import (
        Inbox)
    from shared_engines.events.contracts import (
        EventCatalog)
    from shared_engines.storage.database import (
        SQLiteAdapter)
    from shared_engines.common.clocks import (
        FrozenClock)
    cat = EventCatalog()
    cat.register(
        "agro.sale.created")
    db_red = SQLiteAdapter(
        tmp_path / "rr.db")
    db_nexo = SQLiteAdapter(
        tmp_path / "rrn.db")
    clock = FrozenClock()
    out_red = Outbox(db_red, clock)
    out_red.ensure_schema()
    inbox_nexo = Inbox(
        db_nexo, clock)
    llego = threading.Event()
    recibidos = []

    def handler(ev):
        recibidos.append(
            ev.event_id)
        llego.set()

    bridge = InterAppBridge(
        db=db_red, clock=clock,
        source=out_red)
    bridge.subscribe(
        app_id="nexo",
        event_types=(
            "agro.sale"
            ".created",),
        inbox=inbox_nexo,
        handler=handler)
    stop = threading.Event()
    res = {}
    hilo = threading.Thread(
        target=lambda: res.update(
            bridge.relay_forever(
                stop=stop,
                interval_seconds=(
                    0.05))),
        daemon=True)
    hilo.start()
    ev = cat.build(
        "agro.sale.created",
        aggregate_id="S9",
        payload={"t": 1},
        clock=clock)
    out_red.enqueue(ev)
    assert llego.wait(
        timeout=10), (
        "autonomo no entrego")
    stop.set()
    hilo.join(timeout=5)
    assert not hilo.is_alive(), (
        "bucle no termino")
    assert (res.get(
        "delivered", 0) >= 1), (
        str(res))
    assert (res.get(
        "errors", 0) == 0), (
        str(res))
    print("OK RED-RELAY:"
          " cartero autonomo"
          " entrego, stop limpio,"          " cero errores")
