import pytest
from shared_engines.common.clocks import FrozenClock
from shared_engines.storage.database import SQLiteAdapter
from shared_engines.support.engine import SupportEngine

def _eng(tmp_path):
    return SupportEngine(SQLiteAdapter(tmp_path / "s.db"), FrozenClock())

def test_ticket_lifecycle(tmp_path) -> None:
    eng = _eng(tmp_path)
    t = eng.create_ticket(app_id="nexo", title="Mi cuenta",
                          description="no puedo entrar", client_id="C1")
    assert t["status"] == "OPEN" and t["app_id"] == "nexo"
    a = eng.assign_ticket(ticket_id=t["ticket_id"], agent_id="AG1")
    assert a["status"] == "ASSIGNED" and a["agent_id"] == "AG1"
    r = eng.resolve_ticket(ticket_id=t["ticket_id"], resolution="resuelto")
    assert r["status"] == "RESOLVED"
    c = eng.close_ticket(ticket_id=t["ticket_id"])
    assert c["status"] == "CLOSED"
    print("OK support: ticket OPEN->ASSIGNED->RESOLVED->CLOSED")

def test_cross_app_case(tmp_path) -> None:
    eng = _eng(tmp_path)
    c = eng.create_cross_app_case(apps_involved=["nexo", "axis"],
                                  title="caso transversal fraude")
    assert c["apps_involved"] == ["nexo", "axis"]
    assert c["status"] == "OPEN"
    print("OK support: caso transversal NEXO+AXIS")

def test_escalation_cross_app(tmp_path) -> None:
    eng = _eng(tmp_path)
    t = eng.create_ticket(app_id="nexo", title="tema legal",
                          priority="HIGH")
    e = eng.escalate_ticket(ticket_id=t["ticket_id"], to_app="axis",
                            level="CRITICAL", reason="tema legal")
    assert e["from_app"] == "nexo" and e["to_app"] == "axis"
    got = eng.get_ticket(t["ticket_id"])
    assert got["status"] == "ESCALATED"
    print("OK support: escalamiento NEXO->AXIS")

def test_feedback_satisfaction(tmp_path) -> None:
    eng = _eng(tmp_path)
    t = eng.create_ticket(app_id="subastas", title="envio")
    eng.register_feedback(ticket_id=t["ticket_id"], client_id="C1",
                          score=9, comments="excelente")
    eng.register_feedback(ticket_id=t["ticket_id"], client_id="C2",
                          score=7, comments="bien")
    s = eng.average_satisfaction(app_id="subastas")
    assert s["score"] == 8.0 and s["responses"] == 2
    print("OK support: satisfaccion 8.0 subastas")
