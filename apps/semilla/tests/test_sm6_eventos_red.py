import pytest
from shared_engines.common.clocks import FrozenClock
from apps.semilla.events.contracts import (make_event,
    SEMILLA_TALENT_DETECTED, is_valid_event)
from apps.semilla.infrastructure.messaging.message_bus import SemillaMessageBus
from apps.semilla.services.semilla_bridge import SemillaBridge

def test_catalogo_eventos_semilla() -> None:
    assert is_valid_event(SEMILLA_TALENT_DETECTED)
    ev = make_event(SEMILLA_TALENT_DETECTED,
        student_id="STU-1",
        payload={"category": "MATEMATICAS"})
    assert ev["event"] == SEMILLA_TALENT_DETECTED
    assert ev["source"] == "semilla"
    with pytest.raises(ValueError):
        make_event("EVENTO_FALSO")
    print("OK catalogo: eventos SEMILLA_* validados")

def test_bus_publish_drain() -> None:
    bus = SemillaMessageBus(clock=FrozenClock())
    ev = make_event(SEMILLA_TALENT_DETECTED,
        student_id="STU-2")
    r = bus.publish(ev)
    assert r["buffered"] is True
    assert bus.pending() == 1
    taken = bus.drain()
    assert len(taken) == 1 and bus.pending() == 0
    print("OK bus: publish/drain/pending")

def test_bridge_sin_link_honesto() -> None:
    br = SemillaBridge(clock=FrozenClock())
    st = br.status()
    assert st["link_available"] is False
    r = br.emit("SEMILLA_TALENT_DETECTED",
        student_id="STU-3",
        payload={"category": "ARTE"})
    assert r["buffered"] is True
    f = br.feed_talent(student_id="STU-3",
        category="ARTE", detail="dibujo avanzado")
    assert f["network_history"] is False
    print("OK bridge sin link: buffer honesto")

def test_bridge_con_link_real() -> None:
    llamadas = []
    class FakeLink:
        def record_milestone(self, student_id, kind,
                             detail):
            llamadas.append((student_id, kind, detail))
            return {"ok": True}
    br = SemillaBridge(semilla_link=FakeLink(),
        clock=FrozenClock())
    f = br.feed_talent(student_id="STU-4",
        category="MATEMATICAS",
        detail="olimpiada nacional")
    assert f["network_history"] is True
    assert llamadas[0][1] == "talento"
    f2 = br.feed_certification(student_id="STU-4",
        title="Bachillerato", detail="promedio 9")
    assert f2["network_history"] is True
    assert llamadas[1][1] == "certificacion"
    assert len(br.drain_events()) == 2
    print("OK bridge con link: talento/certificacion -> historial de la Red")

def test_bridge_status() -> None:
    br = SemillaBridge(clock=FrozenClock())
    st = br.status()
    assert "events_pending" in st
    assert "link_available" in st
    print("OK bridge status: observabilidad")
