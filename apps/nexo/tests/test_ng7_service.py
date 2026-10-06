import pytest
from shared_engines.common.clocks import FrozenClock
from shared_engines.storage.database import SQLiteAdapter
from shared_engines.support.engine import SupportEngine
from apps.nexo.domain.customer_service.customer_service_engine import NexoCustomerServiceEngine
from apps.nexo.application.customer_service_use_cases.create_ticket_use_case import CreateTicketUseCase
from apps.nexo.application.customer_service_use_cases.assign_ticket_use_case import AssignTicketUseCase
from apps.nexo.application.customer_service_use_cases.close_ticket_use_case import CloseTicketUseCase
from apps.nexo.application.customer_service_use_cases.escalate_ticket_use_case import EscalateTicketUseCase
from apps.nexo.application.customer_service_use_cases.register_feedback_use_case import RegisterFeedbackUseCase
from apps.nexo.application.customer_service_use_cases.calculate_satisfaction_use_case import CalculateSatisfactionUseCase
from apps.nexo.application.customer_service_use_cases.generate_service_report_use_case import GenerateServiceReportUseCase
from apps.nexo.domain.notifications.notification_engine import NexoNotificationEngine
from apps.nexo.domain.notifications.notification_registry import NexoNotificationRegistry
from apps.nexo.application.notifications_use_cases.create_notification_use_case import CreateNotificationUseCase
from apps.nexo.application.notifications_use_cases.dispatch_notification_use_case import DispatchNotificationUseCase

def _cs(db):
    support = SupportEngine(SQLiteAdapter(db / "s.db"),
                            FrozenClock())
    return NexoCustomerServiceEngine(support)

def test_cs_adapters_full(tmp_path) -> None:
    cs = _cs(tmp_path)
    t = cs.tickets.open_ticket(title="Mi cuenta",
        description="no entro", client_id="C1")
    assert t["app_id"] == "nexo"
    a = cs.tickets.assign(ticket_id=t["ticket_id"],
        agent_id="AG1")
    assert a["status"] == "ASSIGNED"
    r = cs.tickets.resolve(ticket_id=t["ticket_id"],
        resolution="listo")
    assert r["status"] == "RESOLVED"
    c = cs.tickets.close(t["ticket_id"])
    assert c["status"] == "CLOSED"
    t2 = cs.tickets.open_ticket(title="legal",
        priority="HIGH")
    e = cs.escalations.escalate(
        ticket_id=t2["ticket_id"], to_app="axis",
        reason="tema legal")
    assert e["to_app"] == "axis"
    case = cs.cases.open_case(
        apps_involved=["axis", "semilla"],
        title="caso transversal")
    assert case["apps_involved"][0] == "nexo"
    cs.satisfaction.register(ticket_id=t["ticket_id"],
        client_id="C1", score=9)
    avg = cs.satisfaction.average()
    assert avg["score"] == 9.0
    print("OK cs adapters: ciclo completo + escalamiento + caso")

def test_cs_usecases_and_report(tmp_path) -> None:
    cs = _cs(tmp_path)
    t = CreateTicketUseCase(cs.tickets).execute(
        title="problema de pago", client_id="C2")
    AssignTicketUseCase(cs.tickets).execute(
        ticket_id=t["ticket_id"], agent_id="AG2")
    CloseTicketUseCase(cs.tickets).execute(
        ticket_id=t["ticket_id"],
        resolution="solucionado")
    RegisterFeedbackUseCase(
        cs.satisfaction).execute(
        ticket_id=t["ticket_id"], client_id="C2",
        score=8)
    sat = CalculateSatisfactionUseCase(
        cs.satisfaction).execute()
    assert sat["score"] == 8.0
    rep = GenerateServiceReportUseCase(cs).execute()
    assert rep["tickets_total"] == 1
    assert rep["satisfaction"]["score"] == 8.0
    with pytest.raises(ValueError):
        CreateTicketUseCase(cs.tickets).execute(
            title="")
    with pytest.raises(ValueError):
        CloseTicketUseCase(cs.tickets).execute(
            ticket_id=t["ticket_id"], resolution="")
    print("OK cs use cases: flujo completo + reporte + validaciones")

def test_notifications_queue(tmp_path) -> None:
    db = SQLiteAdapter(tmp_path / "n.db")
    clock = FrozenClock()
    sent_log = []
    class FakeChannel:
        def send(self, recipient, subject, body):
            sent_log.append(recipient)
            return {"ok": True}
    eng = NexoNotificationEngine(db, clock,
        channel=FakeChannel())
    uc = CreateNotificationUseCase(eng)
    n1 = uc.execute(recipient="cliente@nexo.sv",
        subject="Factura lista", body="ver",
        channel="email", company_id="EMP-1")
    n2 = uc.execute(recipient="otro@nexo.sv",
        subject="Pago recibido")
    with pytest.raises(ValueError):
        uc.execute(recipient="", subject="x")
    d = DispatchNotificationUseCase(eng).execute()
    assert d["processed"] == 2
    assert d["sent"] == 2
    assert sent_log == ["cliente@nexo.sv",
                        "otro@nexo.sv"]
    reg = NexoNotificationRegistry(db, clock)
    assert reg.counts_by_status().get("SENT") == 2
    print("OK notificaciones: cola + canal falso + registro")

def test_notifications_honesto_y_retry(tmp_path) -> None:
    db = SQLiteAdapter(tmp_path / "n2.db")
    eng = NexoNotificationEngine(db, FrozenClock())
    n = eng.create_notification(recipient="x@y.z",
        subject="s")
    r = eng.dispatch(n["notification_id"])
    assert r["status"] == "FAILED"
    assert r["error"] == "not_configured"
    assert eng.retry_failed() == 1
    d = DispatchNotificationUseCase(eng).execute()
    assert d["processed"] == 1
    assert d["sent"] == 0
    print("OK notificaciones: sin canal honesto + reintento")
