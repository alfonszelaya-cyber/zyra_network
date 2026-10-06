import pytest
from shared_engines.common.clocks import FrozenClock
from shared_engines.storage.database import SQLiteAdapter
from apps.nexo.events.contracts import (make_event,
    NEXO_PAYMENT_RECEIVED)
from apps.nexo.services.boot import (RedEventMapper,
    RedOutboxAdapter, build_runtime)

def test_mapper_construye_event_real():
    mapper = RedEventMapper()
    assert mapper.available is True
    ev_dict = make_event(NEXO_PAYMENT_RECEIVED,
        company_id="EMP-1", payload={"amount": "5"},
        occurred_at=123.0)
    ev = mapper.build(ev_dict)
    assert ev is not None
    assert isinstance(ev, mapper.event_cls)
    print("OK mapper: dict NEXO_* -> Event real")

def test_adapter_fluye_a_outbox_real():
    mapper = RedEventMapper()
    recibidos = []
    class FakeOutbox:
        def enqueue(self, event):
            recibidos.append(event)
    adapter = RedOutboxAdapter(outbox=FakeOutbox(),
                               mapper=mapper)
    assert adapter.connected is True
    ev_dict = make_event(NEXO_PAYMENT_RECEIVED,
        company_id="EMP-2", payload={"x": "1"},
        occurred_at=1.0)
    assert adapter.append(ev_dict) is True
    assert len(recibidos) == 1
    assert isinstance(recibidos[0], mapper.event_cls)
    print("OK adapter: NEXO_* llega al outbox como Event real")

def test_bus_hacia_la_red():
    mapper = RedEventMapper()
    recibidos = []
    class FakeOutbox:
        def enqueue(self, event):
            recibidos.append(event)
    from apps.nexo.infrastructure.messaging.message_bus import NexoMessageBus
    bus = NexoMessageBus(outbox=RedOutboxAdapter(
        outbox=FakeOutbox(), mapper=mapper),
        clock=FrozenClock())
    ev = make_event(NEXO_PAYMENT_RECEIVED,
        company_id="EMP-3", payload={"a": "1"})
    r = bus.publish(ev)
    assert r["delivered_to_network"] is True
    assert r["buffered"] is False
    assert bus.pending() == 0
    assert len(recibidos) == 1
    print("OK bus->Red: cartero recibe el evento")

def test_build_runtime_conectado(tmp_path):
    class FakeClient:
        pass
    rt = build_runtime(db=SQLiteAdapter(tmp_path / "b.db"),
        clock=FrozenClock(), client=FakeClient())
    assert rt.link is not None
    assert rt.verification.mode == "nexo_link"
    assert rt.outbox_adapter is not None
    st = rt.status()
    assert "events_pending" in st
    r = rt.emit(NEXO_PAYMENT_RECEIVED,
        company_id="EMP-4", payload={"m": "1"})
    assert (r["delivered_to_network"] is True
            or r["buffered"] is True)
    print("OK build_runtime: link+verificacion+outbox")

def test_build_runtime_sin_red_honesto():
    rt = build_runtime(clock=FrozenClock())
    assert rt.verification.mode == "not_configured"
    assert rt.link is None
    r = rt.emit(NEXO_PAYMENT_RECEIVED,
        company_id="EMP-5", payload={})
    assert r["buffered"] is True
    print("OK sin Red: degradacion honesta a buffer")
