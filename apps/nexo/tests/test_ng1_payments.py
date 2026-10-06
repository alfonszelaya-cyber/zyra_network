import pytest
from shared_engines.common.clocks import FrozenClock
from shared_engines.storage.database import SQLiteAdapter
from apps.nexo.events.contracts import (make_event,
    NEXO_PAYMENT_RECEIVED, is_valid_event)
from apps.nexo.infrastructure.messaging.message_bus import NexoMessageBus
from apps.nexo.domain.payments.payment_engine import NexoPaymentEngine
from apps.nexo.domain.payments.payment_validation import NexoPaymentValidation
from apps.nexo.domain.payments.payment_reconciliation import NexoPaymentReconciliation
from apps.nexo.domain.audit.audit_engine import NexoAuditEngine
from apps.nexo.domain.audit.audit_registry import NexoAuditRegistry
from apps.nexo.domain.audit.audit_validation import NexoAuditValidation
from apps.nexo.services.transversal.currency.currency_gateway import NexoCurrencyGateway
from apps.nexo.application.payments_use_cases.process_payment_use_case import ProcessPaymentUseCase
from apps.nexo.application.payments_use_cases.reconcile_payment_use_case import ReconcilePaymentUseCase
from apps.nexo.application.payments_use_cases.validate_payment_use_case import ValidatePaymentUseCase

def test_events_catalog_and_bus() -> None:
    assert is_valid_event(NEXO_PAYMENT_RECEIVED)
    ev = make_event(NEXO_PAYMENT_RECEIVED,
                    company_id="EMP-001",
                    payload={"amount": "10"})
    assert ev["event"] == NEXO_PAYMENT_RECEIVED
    assert ev["source"] == "nexo"
    bus = NexoMessageBus(clock=FrozenClock())
    res = bus.publish(ev)
    assert res["buffered"] is True
    assert res["delivered_to_network"] is False
    taken = bus.drain()
    assert len(taken) == 1 and bus.pending() == 0
    print("OK eventos+bus: catalogo y publish/drain")

def test_payment_flow_use_case(tmp_path) -> None:
    db = SQLiteAdapter(tmp_path / "pay.db")
    clock = FrozenClock()
    bus = NexoMessageBus(clock=clock)
    eng = NexoPaymentEngine(db, clock, bus=bus)
    val = NexoPaymentValidation(db, clock,
        currency_gateway=NexoCurrencyGateway())
    uc = ProcessPaymentUseCase(val, eng)
    r = uc.execute(company_id="EMP-001",
                   direction="INCOMING",
                   amount="1500.75",
                   counterparty="Cliente X",
                   reference="F-2001",
                   method="transferencia")
    assert r["processed"] is True
    assert r["payment"]["amount"] == "1500.75"
    assert r["payment"]["event_published"] is True
    r2 = uc.execute(company_id="EMP-001",
                    direction="INCOMING", amount="-5",
                    counterparty="Y", reference="F-2002")
    assert r2["processed"] is False
    r3 = uc.execute(company_id="EMP-001",
                    direction="INCOMING", amount="10",
                    counterparty="Z", reference="")
    assert r3["processed"] is False
    assert bus.pending() == 1
    evs = bus.drain()
    assert evs[0]["event"] == NEXO_PAYMENT_RECEIVED
    print("OK pagos: flujo completo + evento + validaciones")

def test_reconciliation(tmp_path) -> None:
    db = SQLiteAdapter(tmp_path / "rec.db")
    clock = FrozenClock()
    eng = NexoPaymentEngine(db, clock)
    rec_eng = NexoPaymentReconciliation(db, clock)
    p1 = eng.record_payment(company_id="EMP-9",
        direction="INCOMING", amount="100",
        reference="R-1", counterparty="A")
    p2 = eng.record_payment(company_id="EMP-9",
        direction="INCOMING", amount="200",
        reference="R-2", counterparty="B")
    p3 = eng.record_payment(company_id="EMP-9",
        direction="INCOMING", amount="300",
        reference="R-3", counterparty="C")
    uc = ReconcilePaymentUseCase(rec_eng, eng)
    r = uc.execute(company_id="EMP-9", statement=[
        {"reference": "R-1", "amount": "100"},
        {"reference": "R-2", "amount": "999"}])
    assert r["matched"] == 1 and r["unmatched"] == 2
    assert eng.get_payment(
        p1["payment_id"])["status"] == "RECONCILED"
    assert eng.get_payment(
        p2["payment_id"])["status"] == "RECORDED"
    print("OK conciliacion: match exacto + estados")

def test_audit_domain(tmp_path) -> None:
    db = SQLiteAdapter(tmp_path / "ad.db")
    clock = FrozenClock()
    eng = NexoAuditEngine(db, clock)
    a1 = eng.audit(event="PERIOD_CLOSED",
                   actor="contador", entity="EMP-1",
                   after={"periodo": "2026-03"})
    assert a1["audit_id"].startswith("AUD-")
    eng.audit(event="JOURNAL_POSTED", actor="sistema",
              entity="EMP-1")
    reg = NexoAuditRegistry(db, clock)
    assert reg.counts_by_event().get("JOURNAL_POSTED") == 1
    assert reg.last_for_entity("EMP-1") is not None
    v = NexoAuditValidation()
    assert v.validate_record({"event": "X", "actor": "a",
                              "entity": "e"})["valid"] is True
    assert v.validate_record({"event": "X"})["valid"] is False
    print("OK auditoria dominio: engine+registry+validacion")
