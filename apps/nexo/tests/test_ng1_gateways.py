import pytest
from shared_engines.common.clocks import FrozenClock
from shared_engines.storage.database import SQLiteAdapter
from apps.nexo.services.transversal.currency.currency_gateway import NexoCurrencyGateway
from apps.nexo.services.transversal.finance.finance_gateway import NexoFinanceGateway
from apps.nexo.services.transversal.audit.audit_gateway import NexoAuditGateway
from apps.nexo.services.transversal.ai.ai_gateway import NexoAIGateway

def test_currency_gateway_decimal(tmp_path) -> None:
    gw = NexoCurrencyGateway()
    assert gw.mode == "static_fallback"
    r = gw.convert("100", "USD", "EUR")
    assert r["converted"] == "92.00"
    assert r["source"] == "static_fallback"
    q = gw.quote("USD", "GTQ")
    assert q["rate"] == "7.75"
    sup = gw.supported()
    assert "USD" in sup and "BTC" in sup
    print("OK currency gateway: Decimal 100 USD -> 92.00 EUR")

def test_finance_gateway_honesto() -> None:
    gw = NexoFinanceGateway()
    caps = gw.capabilities()
    assert caps == {"finance_master": False,
                    "declarations": False,
                    "tax_declarations": False,
                    "fiscal_documents": False}
    r = gw.declare_tax(period="2026-03")
    assert r["status"] == "not_configured"
    print("OK finance gateway: estado honesto sin engines")

def test_audit_gateway_registra(tmp_path) -> None:
    db = SQLiteAdapter(tmp_path / "aud.db")
    gw = NexoAuditGateway(db=db, clock=FrozenClock())
    r1 = gw.record_event(event="TEST_EVENTO",
                         actor="usuario1",
                         entity="EMP-001",
                         after={"monto": "100"})
    assert r1["recorded"] is True
    r2 = gw.record_event(event="TEST_EVENTO_2",
                         actor="auditor",
                         entity="EMP-002")
    assert r2["recorded"] is True
    assert len(gw.entries()) == 2
    print("OK audit gateway: 2 registros con buffer/modo")

def test_ai_gateway_clasifica() -> None:
    gw = NexoAIGateway()
    r = gw.classify_document(
        "Factura de venta por servicios de consultoria")
    assert r["category"] == "venta"
    assert r["source"] == "rules_fallback"
    r2 = gw.classify_document(
        "Pago a proveedor por compra de materiales")
    assert r2["category"] in ("pago", "compra")
    print("OK ai gateway: clasificacion por reglas marcada")
