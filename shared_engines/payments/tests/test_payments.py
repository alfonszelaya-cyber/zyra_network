
"""RED-6 COMPLETO: pagos, servicios, QR, telefono, remesas, marketplace."""
from __future__ import annotations

from decimal import Decimal

import pytest

from shared_engines.audit.chain import AuditTrail
from shared_engines.common.clocks import FrozenClock
from shared_engines.events.contracts import EventCatalog
from shared_engines.events.outbox import Outbox
from shared_engines.payments.engine import PaymentsEngine
from shared_engines.payments.errors import (
    DisputeWindowClosedError,
    InstrumentInactiveError,
    PaymentStateError,
    QRRequestUnavailableError,
)
from shared_engines.storage.database import SQLiteAdapter

EVENTS = (
    "identity.registered", "identity.status_changed",
    "currency.quote.issued", "currency.conversion.recorded",
    "payments.payment.created", "payments.payment.held",
    "payments.payment.disputed", "payments.payment.released",
    "payments.payment.refunded", "payments.qr.generated",
    "payments.remittance.routed",
)

RATES_FX = {
    "USD/GTQ": "7.75",
    "GTQ/USD": "0.128",
    "BTC/USD": "84780",
}


def _engine(tmp_path, clock=None, currency=None):
    db = SQLiteAdapter(tmp_path / "pay.db")
    ck = clock or FrozenClock()
    audit = AuditTrail(db, ck)
    outbox = Outbox(db, ck)
    outbox.ensure_schema()
    catalog = EventCatalog()
    for e in EVENTS:
        catalog.register(e)
    eng = PaymentsEngine(db=db, clock=ck, audit=audit, outbox=outbox, catalog=catalog, currency=currency)
    return eng, db, ck


def _full(tmp_path):
    from shared_engines.currency.engine import CurrencyEngine
    from shared_engines.currency.rates import StaticTableRateProvider
    from shared_engines.identity.contracts import IdentityKind
    from shared_engines.identity.engine import IdentityEngine
    from shared_engines.verification.signatures import Ed25519Signer
    db = SQLiteAdapter(tmp_path / "full.db")
    clock = FrozenClock()
    audit = AuditTrail(db, clock)
    outbox = Outbox(db, clock)
    outbox.ensure_schema()
    catalog = EventCatalog()
    for e in EVENTS:
        catalog.register(e)
    identity = IdentityEngine(db=db, clock=clock, audit=audit, outbox=outbox, catalog=catalog)
    signer, _ = Ed25519Signer.generate()
    fx = CurrencyEngine(db=db, clock=clock, providers=[StaticTableRateProvider(RATES_FX, clock)], signer=signer, audit=audit, outbox=outbox, catalog=catalog, identity=identity)
    eng = PaymentsEngine(db=db, clock=clock, audit=audit, outbox=outbox, catalog=catalog, currency=fx)
    juan = identity.register_identity(kind=IdentityKind.PERSON, display_name="Juan", actor="registrar").zid
    pedro = identity.register_identity(kind=IdentityKind.PERSON, display_name="Pedro", actor="registrar").zid
    return eng, db, clock, juan, pedro


def test_instrument_never_stores_detail(tmp_path) -> None:
    eng, db, _ = _engine(tmp_path)
    inst = eng.register_instrument(zid="ZID-a", kind="card_debit", label="Mi tarjeta", masked_ref="****4242", detail_ref="4111111111114242")
    row = db.query_one("SELECT * FROM payment_instruments WHERE instrument_id = ?", (inst["instrument_id"],))
    assert "4111111111114242" not in str(dict(row))
    assert row["masked_ref"] == "****4242"
    eng.deactivate_instrument(zid="ZID-a", instrument_id=inst["instrument_id"])
    with pytest.raises(InstrumentInactiveError):
        eng.create_payment(payer_zid="ZID-a", payee_zid="ZID-b", amount=Decimal("10.00"), currency="USD", instrument_id=inst["instrument_id"], purpose="x")
    print("OK RED-6: instrumentos solo referencia enmascarada")


def test_escrow_hold_release_dispute(tmp_path) -> None:
    eng, db, _ = _engine(tmp_path)
    inst = eng.register_instrument(zid="ZID-a", kind="bank_account", label="Banco", masked_ref="****0001")
    pay = eng.create_payment(payer_zid="ZID-a", payee_zid="ZID-b", amount=Decimal("100.00"), currency="USD", instrument_id=inst["instrument_id"], purpose="compra subasta")
    assert pay["state"] == "CREATED"
    held = eng.mark_held(pay["payment_id"], hold_ref="HOLD-77")
    assert held["state"] == "HELD"
    d = eng.open_dispute(pay["payment_id"], reason="no era lo que queria")
    assert d["state"] == "DISPUTE"
    ref = eng.resolve_dispute(pay["payment_id"], outcome="refund")
    assert ref["state"] == "REFUNDED"
    evs = db.query_all("SELECT event_type FROM events_outbox WHERE aggregate_id = ?", (pay["payment_id"],))
    tipos = [str(r["event_type"]) for r in evs]
    assert "payments.payment.disputed" in tipos
    assert "payments.payment.refunded" in tipos
    print("OK RED-6: escrow 3 dias habiles con reclamo y reembolso")


def test_dispute_window_closes_and_autorelease(tmp_path) -> None:
    eng, db, ck = _engine(tmp_path)
    inst = eng.register_instrument(zid="ZID-a", kind="card_credit", label="C", masked_ref="****1111")
    p1 = eng.create_payment(payer_zid="ZID-a", payee_zid="ZID-b", amount="20.00", currency="USD", instrument_id=inst["instrument_id"], purpose="p1")
    eng.mark_held(p1["payment_id"], hold_ref="H1")
    ck.advance(3600 * 24 * 4)
    with pytest.raises(DisputeWindowClosedError):
        eng.open_dispute(p1["payment_id"], reason="tarde")
    released = eng.auto_release_due()
    assert p1["payment_id"] in released
    print("OK RED-6: ventana cerrada + auto-release")


def test_pay_service_bills_with_service_fee(tmp_path) -> None:
    eng, db, _ = _engine(tmp_path)
    inst = eng.register_instrument(zid="ZID-a", kind="digital_wallet", label="W", masked_ref="****w1")
    agua = eng.pay_service(payer_zid="ZID-a", service_type="water", service_account="LECT-5521", amount="12.50", currency="USD", instrument_id=inst["instrument_id"], reference="RECIBO-099")
    assert agua["state"] == "RELEASED"
    assert agua["service_type"] == "water"
    assert Decimal(agua["fee_send"]) == Decimal("0.1625"), str(agua)
    luz = eng.pay_service(payer_zid="ZID-a", service_type="electricity", service_account="MED-773", amount="35.00", currency="USD", instrument_id=inst["instrument_id"])
    tel = eng.pay_service(payer_zid="ZID-a", service_type="phone", service_account="7000-1234", amount="10.00", currency="USD", instrument_id=inst["instrument_id"])
    cable = eng.pay_service(payer_zid="ZID-a", service_type="cable", service_account="SUS-42", amount="25.00", currency="USD", instrument_id=inst["instrument_id"])
    estados = {agua["state"], luz["state"], tel["state"], cable["state"]}
    assert estados == {"RELEASED"}
    with pytest.raises(Exception):
        eng.pay_service(payer_zid="ZID-a", service_type="yate", service_account="X", amount="1", currency="USD", instrument_id=inst["instrument_id"])
    print("OK RED-6: servicios agua/luz/telefono/cable con comision SERVICE")


def test_qr_and_barcode_flow(tmp_path) -> None:
    eng, db, ck = _engine(tmp_path)
    inst = eng.register_instrument(zid="ZID-comprador", kind="card_debit", label="T", masked_ref="****9")
    qr = eng.generate_payment_qr(payee_zid="ZID-vendedor", purpose="puesto mercado", amount=Decimal("15.00"), currency="USD")
    assert qr["qr_token"].startswith("QR-")
    pay = eng.pay_by_code(payer_zid="ZID-comprador", code=qr["payload_b64"], instrument_id=inst["instrument_id"])
    assert pay["state"] == "RELEASED"
    assert pay["payee_zid"] == "ZID-vendedor"
    assert Decimal(pay["amount"]) == Decimal("15.00")
    with pytest.raises(QRRequestUnavailableError):
        eng.pay_by_code(payer_zid="ZID-comprador", code=qr["qr_token"], instrument_id=inst["instrument_id"])
    qr2 = eng.generate_payment_qr(payee_zid="ZID-vendedor", purpose="abierto")
    ck.advance(1200)
    with pytest.raises(QRRequestUnavailableError):
        eng.pay_by_code(payer_zid="ZID-comprador", code=qr2["qr_token"], instrument_id=inst["instrument_id"], amount="5")
    print("OK RED-6: QR/codigo de barras un solo uso y expiracion")


def test_qr_open_amount_and_phone(tmp_path) -> None:
    eng, db, _ = _engine(tmp_path)
    inst = eng.register_instrument(zid="ZID-a", kind="card_debit", label="T", masked_ref="****8")
    eng.register_phone_alias(zid="ZID-pedro", phone="+50370001234")
    res = eng.resolve_phone("+50370001234")
    assert res["zid"] == "ZID-pedro"
    assert res["verified"] is False
    qr = eng.generate_payment_qr(payee_zid="ZID-pedro", purpose="colectivia")
    pay = eng.pay_by_code(payer_zid="ZID-a", code=qr["qr_token"], instrument_id=inst["instrument_id"], amount="7.25", currency="USD")
    assert Decimal(pay["amount"]) == Decimal("7.25")
    envio = eng.pay_by_phone(payer_zid="ZID-a", phone="+50370001234", amount="40.00", currency="USD", instrument_id=inst["instrument_id"])
    assert envio["payee_zid"] == "ZID-pedro"
    assert envio["state"] == "RELEASED"
    with pytest.raises(Exception):
        eng.pay_by_phone(payer_zid="ZID-a", phone="+1999", amount="1", currency="USD", instrument_id=inst["instrument_id"])
    print("OK RED-6: pago por telefono y QR de monto abierto")


def test_menu_remesa_internacional(tmp_path) -> None:
    eng, db, ck, juan, pedro = _full(tmp_path)
    q = eng.transfer_quote(sender_zid=juan, send_currency="USD", receive_currency="GTQ", amount="100.00")
    assert q["corridor"] == "INTERNATIONAL"
    assert Decimal(q["rate"]) == Decimal("7.75")
    assert Decimal(q["receive_amount"]) == Decimal("775")
    assert Decimal(q["fee_send"]) == Decimal("5.00")
    assert Decimal(q["total_debited"]) == Decimal("105.00")
    assert "cash_pickup" in q["delivery_methods"]
    print("OK RED-6 MENU: USA->GT 100 USD = 775 GTQ, comision 5.00")


def test_menu_remesa_domestica(tmp_path) -> None:
    eng, db, ck, juan, pedro = _full(tmp_path)
    q = eng.transfer_quote(sender_zid=juan, send_currency="USD", receive_currency="USD", amount="100.00")
    assert q["corridor"] == "DOMESTIC"
    assert Decimal(q["rate"]) == Decimal(1)
    assert Decimal(q["fee_send"]) == Decimal("1.50")
    print("OK RED-6 MENU: domestico tasa 1, comision 1.50")


def test_envio_usa_a_gtq(tmp_path) -> None:
    eng, db, ck, juan, pedro = _full(tmp_path)
    inst = eng.register_instrument(zid=juan, kind="card_debit", label="Tarjeta USA", masked_ref="****7777")
    envio = eng.send_money(payer_zid=juan, payee_zid=pedro, amount="100.00", currency="USD", instrument_id=inst["instrument_id"], receive_currency="GTQ")
    assert envio["state"] == "RELEASED"
    assert envio["corridor"] == "INTERNATIONAL"
    assert envio["receive_currency"] == "GTQ"
    assert Decimal(envio["receive_amount"]) == Decimal("775")
    assert envio["conversion_id"].startswith("CNV-")
    assert Decimal(envio["fee_send"]) == Decimal("5.00")
    evs = db.query_all("SELECT event_type FROM events_outbox WHERE aggregate_id = ?", (envio["payment_id"],))
    tipos = [str(r["event_type"]) for r in evs]
    assert "payments.remittance.routed" in tipos
    print("OK RED-6: 100 USD -> 775 GTQ con conversion y evento al cartero")


def test_envio_btc_recibe_usd(tmp_path) -> None:
    eng, db, ck, juan, pedro = _full(tmp_path)
    inst = eng.register_instrument(zid=juan, kind="crypto_wallet", label="BTC", masked_ref="bc1q****x9")
    envio = eng.send_money(payer_zid=juan, payee_zid=pedro, amount="0.001", currency="BTC", instrument_id=inst["instrument_id"], receive_currency="USD")
    assert envio["corridor"] == "INTERNATIONAL"
    assert envio["receive_currency"] == "USD"
    assert Decimal(envio["receive_amount"]) == Decimal("84.78")
    assert Decimal(envio["fee_send"]) > 0
    q = eng.transfer_quote(sender_zid=juan, send_currency="BTC", receive_currency="USD", amount="0.001")
    assert Decimal(q["rate"]) == Decimal("84780")
    print("OK RED-6: 0.001 BTC -> 84.78 USD, comision convertida honestamente")


def test_remesa_domestica_directa(tmp_path) -> None:
    eng, db, ck, juan, pedro = _full(tmp_path)
    inst = eng.register_instrument(zid=juan, kind="bank_account", label="Banco SV", masked_ref="****0001")
    envio = eng.send_money(payer_zid=juan, payee_zid=pedro, amount="50.00", currency="USD", instrument_id=inst["instrument_id"])
    assert envio["corridor"] == "DOMESTIC"
    assert envio["receive_currency"] == "USD"
    assert Decimal(envio["receive_amount"]) == Decimal("50.00")
    assert Decimal(envio["fee_send"]) == Decimal("1.00")
    assert envio["conversion_id"] is None
    print("OK RED-6: envio mismo pais sin conversion, comision 1.00")


def test_marketplace_fees_buyer_seller_shipping(tmp_path) -> None:
    eng, db, ck, juan, pedro = _full(tmp_path)
    f = eng.marketplace_fees(sale_amount="200.00", with_shipping_label=True)
    assert Decimal(f["buyer_fee"]) == Decimal("4.00")
    assert Decimal(f["seller_fee"]) == Decimal("6.00")
    assert Decimal(f["shipping_label_fee"]) == Decimal("1.00")
    assert Decimal(f["buyer_total"]) == Decimal("204.00")
    assert Decimal(f["seller_net"]) == Decimal("193.00")
    f2 = eng.marketplace_fees(sale_amount="200.00", with_shipping_label=False)
    assert Decimal(f2["seller_net"]) == Decimal("194.00")
    print("OK RED-6 MARKETPLACE: comprador 2%, vendedor 3%, etiqueta 1.00")
