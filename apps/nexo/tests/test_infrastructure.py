import importlib
from apps.nexo.infrastructure.messaging.message_bus import NexoMessageBus
from apps.nexo.events.contracts import (make_event,
    NEXO_PERIOD_CLOSED)

def test_infraestructura_clases():
    st = importlib.import_module(
        "apps.nexo.infrastructure.persistence.nexo_store")
    lk = importlib.import_module(
        "apps.nexo.services.nexo_link")
    nc = importlib.import_module(
        "apps.nexo.infrastructure.network.network_client")
    assert hasattr(st, "NexoStore")
    assert hasattr(lk, "NexoLink")
    assert hasattr(nc, "NetworkClient")
    print("OK infra: NexoStore/NexoLink/NetworkClient")

def test_bus_publica_y_drena():
    bus = NexoMessageBus()
    ev = make_event(NEXO_PERIOD_CLOSED,
                    company_id="EMP-1")
    r = bus.publish(ev)
    assert r["buffered"] is True
    assert bus.pending() == 1
    assert len(bus.drain()) == 1
    assert bus.pending() == 0
    print("OK infra: bus publish/drain")
