
"""RED-6: Motor financiero transversal de la Red.

LA RED NO ES BANCO: no custodia dinero. Es el PUENTE.
Registra instrumentos (solo referencia enmascarada + hash),
gobierna el ciclo del pago con escrow de 3 dias habiles
(hold_ref = referencia EXTERNA del proveedor que si
retiene), paga servicios basicos, QR/codigo de barras de
un solo uso, pago por telefono, remesas con menu de
cotizacion y comisiones por tipo. TODA conversion se
delega al CurrencyEngine. Montos de comision = PLACEHOLDER
del dueno (FEE_SCHEDULE y MARKETPLACE_FEES, un solo lugar).
"""
from __future__ import annotations

import base64
import hashlib
import re
from decimal import Decimal

from shared_engines.audit.chain import AuditTrail
from shared_engines.common.clocks import Clock
from shared_engines.common.errors import ValidationError
from shared_engines.common.identifiers import new_id
from shared_engines.common.serialization import canonical_json_dumps
from shared_engines.common.validation import require_non_empty_str
from shared_engines.events.contracts import EventCatalog
from shared_engines.events.outbox import Outbox
from shared_engines.payments.errors import (
    DisputeWindowClosedError,
    InstrumentInactiveError,
    PaymentStateError,
    QRRequestUnavailableError,
    UnknownInstrumentError,
    UnknownPaymentError,
)
from shared_engines.storage.database import Database
from shared_engines.storage.migrations import (
    Migration,
    MigrationRunner,
)

EVENT_PAYMENT_CREATED = "payments.payment.created"
EVENT_PAYMENT_HELD = "payments.payment.held"
EVENT_PAYMENT_DISPUTED = "payments.payment.disputed"
EVENT_PAYMENT_RELEASED = "payments.payment.released"
EVENT_PAYMENT_REFUNDED = "payments.payment.refunded"
EVENT_QR_GENERATED = "payments.qr.generated"
EVENT_REMITTANCE_ROUTED = "payments.remittance.routed"

INSTRUMENT_KINDS = (
    "card_debit", "card_credit", "bank_account",
    "digital_wallet", "crypto_wallet", "cash_pickup", "other",
)
SERVICE_TYPES = (
    "water", "electricity", "cable", "phone",
    "internet", "gas", "rent", "school", "taxes", "other",
)
DELIVERY_METHODS = (
    "bank_deposit", "cash_pickup", "digital_wallet",
    "crypto_wallet", "home_delivery",
)

STATE_CREATED = "CREATED"
STATE_HELD = "HELD"
STATE_DISPUTE = "DISPUTE"
STATE_RELEASED = "RELEASED"
STATE_REFUNDED = "REFUNDED"

FEE_SCHEDULE = {
    "INTERNATIONAL": {"flat_usd": Decimal("3.00"), "pct": Decimal("0.02")},
    "DOMESTIC": {"flat_usd": Decimal("0.50"), "pct": Decimal("0.01")},
    "SERVICE": {"flat_usd": Decimal("0.10"), "pct": Decimal("0.005")},
}
MARKETPLACE_FEES = {
    "buyer_pct": Decimal("0.02"),
    "seller_pct": Decimal("0.03"),
    "shipping_label_fee_usd": Decimal("1.00"),
}

PAYMENT_MIGRATIONS = (
    Migration(1, "payment_instruments", (
        "CREATE TABLE payment_instruments (instrument_id TEXT PRIMARY KEY, zid TEXT NOT NULL, kind TEXT NOT NULL, label TEXT NOT NULL, masked_ref TEXT NOT NULL, detail_hash TEXT NOT NULL, active INTEGER NOT NULL DEFAULT 1, created_at REAL NOT NULL)",
    )),
    Migration(2, "payments", (
        "CREATE TABLE payments (payment_id TEXT PRIMARY KEY, payer_zid TEXT NOT NULL, payee_zid TEXT NOT NULL, amount TEXT NOT NULL, currency TEXT NOT NULL, receive_currency TEXT NOT NULL DEFAULT '', receive_amount TEXT, conversion_id TEXT, corridor TEXT, fee_send TEXT, instrument_id TEXT NOT NULL, purpose TEXT NOT NULL, hold_ref TEXT, state TEXT NOT NULL, auto_release_at REAL NOT NULL, dispute_reason TEXT, dispute_opened_at REAL, created_at REAL NOT NULL, updated_at REAL NOT NULL)",
        "CREATE INDEX payments_payer ON payments (payer_zid, created_at)",
        "CREATE INDEX payments_state ON payments (state, auto_release_at)",
    )),
    Migration(3, "payment_requests", (
        "CREATE TABLE payment_requests (qr_token TEXT PRIMARY KEY, payee_zid TEXT NOT NULL, amount TEXT, currency TEXT, purpose TEXT NOT NULL, expires_at REAL NOT NULL, used_by_payment TEXT, created_at REAL NOT NULL)",
    )),
    Migration(4, "phone_aliases", (
        "CREATE TABLE phone_aliases (phone TEXT PRIMARY KEY, zid TEXT NOT NULL, verified INTEGER NOT NULL DEFAULT 0, created_at REAL NOT NULL)",
    )),
)


def add_business_days(start_ts: float, days: int) -> float:
    import datetime as _dt
    d = _dt.datetime.fromtimestamp(start_ts, tz=_dt.timezone.utc).date()
    added = 0
    while added < days:
        d += _dt.timedelta(days=1)
        if d.weekday() < 5:
            added += 1
    return _dt.datetime(d.year, d.month, d.day, tzinfo=_dt.timezone.utc).timestamp()


def _norm_phone(phone: str) -> str:
    p = phone.strip()
    if not re.fullmatch(r"\+?[0-9]{8,15}", p):
        raise ValidationError("phone must be 8-15 digits (optional +)")
    return p


class PaymentsEngine:
    """RED-6: puente financiero. Informa, gobierna, protege. Nunca custodia."""

    def __init__(self, *, db: Database, clock: Clock, audit: AuditTrail, outbox: Outbox, catalog: EventCatalog, currency=None) -> None:
        self._db = db
        self._clock = clock
        self._audit = audit
        self._outbox = outbox
        self._catalog = catalog
        self._currency = currency
        for et in (EVENT_PAYMENT_CREATED, EVENT_PAYMENT_HELD, EVENT_PAYMENT_DISPUTED, EVENT_PAYMENT_RELEASED, EVENT_PAYMENT_REFUNDED, EVENT_QR_GENERATED, EVENT_REMITTANCE_ROUTED):
            try:
                self._catalog.register(et)
            except Exception:
                pass
        MigrationRunner(db, "payments.core", PAYMENT_MIGRATIONS).run(clock)

    def _emit(self, event_type, payment_id, payload):
        ev = self._catalog.build(event_type, aggregate_id=payment_id, payload=payload, clock=self._clock)
        self._outbox.enqueue(ev)

    def _check_instrument(self, payer_zid: str, instrument_id: str) -> None:
        inst = self._db.query_one("SELECT * FROM payment_instruments WHERE instrument_id = ? AND zid = ?", (instrument_id, payer_zid))
        if inst is None:
            raise UnknownInstrumentError("unknown instrument: " + instrument_id)
        if not inst["active"]:
            raise InstrumentInactiveError("instrument inactive: " + instrument_id)

    def register_instrument(self, *, zid: str, kind: str, label: str, masked_ref: str, detail_ref: str = "") -> dict:
        require_non_empty_str(zid, "zid")
        if kind not in INSTRUMENT_KINDS:
            raise ValidationError("unknown instrument kind: " + kind)
        require_non_empty_str(label, "label")
        require_non_empty_str(masked_ref, "masked_ref")
        detail_hash = hashlib.sha256(detail_ref.encode("utf-8")).hexdigest() if detail_ref else ""
        instrument_id = "PMT-" + new_id()
        now = self._clock.now()
        with self._db.transaction() as cursor:
            cursor.execute("INSERT INTO payment_instruments (instrument_id, zid, kind, label, masked_ref, detail_hash, active, created_at) VALUES (?, ?, ?, ?, ?, ?, 1, ?)", (instrument_id, zid, kind, label, masked_ref, detail_hash, now))
        self._audit.append(event_type="payments.instrument.registered", actor=zid, subject=instrument_id, payload={"kind": kind})
        return {"instrument_id": instrument_id, "kind": kind, "label": label, "masked_ref": masked_ref, "active": True}

    def list_instruments(self, *, zid: str) -> tuple:
        rows = self._db.query_all("SELECT * FROM payment_instruments WHERE zid = ? ORDER BY created_at", (zid,))
        return tuple({"instrument_id": str(r["instrument_id"]), "kind": str(r["kind"]), "label": str(r["label"]), "masked_ref": str(r["masked_ref"]), "active": bool(r["active"])} for r in rows)

    def deactivate_instrument(self, *, zid: str, instrument_id: str) -> None:
        row = self._db.query_one("SELECT * FROM payment_instruments WHERE instrument_id = ? AND zid = ?", (instrument_id, zid))
        if row is None:
            raise UnknownInstrumentError("unknown instrument: " + instrument_id)
        self._db.execute("UPDATE payment_instruments SET active = 0 WHERE instrument_id = ?", (instrument_id,))
        self._audit.append(event_type="payments.instrument.deactivated", actor=zid, subject=instrument_id, payload={})

    def _quote_rate(self, base: str, quote_ccy: str, zid: str):
        if self._currency is None:
            raise PaymentStateError("currency engine not wired")
        signed = self._currency.quote(base=base, quote_ccy=quote_ccy, requester_zid=zid)
        return signed.quote.rate, signed.quote.source

    def _flat_in(self, send_ccy: str, zid: str, flat_usd: Decimal) -> Decimal:
        if send_ccy == "USD":
            return flat_usd
        rate_to_usd, _ = self._quote_rate(send_ccy, "USD", zid)
        return flat_usd / rate_to_usd

    def transfer_quote(self, *, sender_zid: str, send_currency: str, receive_currency: str, amount) -> dict:
        """MENU DE REMESAS: cotiza sin mover dinero."""
        require_non_empty_str(sender_zid, "sender_zid")
        send_ccy = send_currency.upper().strip()
        recv_ccy = receive_currency.upper().strip()
        amt = amount if isinstance(amount, Decimal) else Decimal(str(amount))
        if not amt.is_finite() or amt <= 0:
            raise ValidationError("amount must be positive")
        if send_ccy == recv_ccy:
            corridor = "DOMESTIC"
            rate = Decimal(1)
            source = "same-currency"
        else:
            corridor = "INTERNATIONAL"
            rate, source = self._quote_rate(send_ccy, recv_ccy, sender_zid)
        sched = FEE_SCHEDULE[corridor]
        fee_send = self._flat_in(send_ccy, sender_zid, sched["flat_usd"]) + amt * sched["pct"]
        return {"corridor": corridor, "send_currency": send_ccy, "receive_currency": recv_ccy, "send_amount": str(amt), "fee_send": str(fee_send), "total_debited": str(amt + fee_send), "rate": str(rate), "rate_source": source, "receive_amount": str(amt * rate), "delivery_methods": DELIVERY_METHODS, "note": "La Red es puente: retencion y liquidacion las ejecutan proveedores externos."}

    def create_payment(self, *, payer_zid: str, payee_zid: str, amount, currency: str, instrument_id: str, purpose: str, escrow: bool = True, auto_release_business_days: int = 3) -> dict:
        require_non_empty_str(payer_zid, "payer_zid")
        require_non_empty_str(payee_zid, "payee_zid")
        if payer_zid == payee_zid:
            raise ValidationError("payer and payee must differ")
        amt = amount if isinstance(amount, Decimal) else Decimal(str(amount))
        if not amt.is_finite() or amt <= 0:
            raise ValidationError("amount must be positive and finite")
        require_non_empty_str(currency, "currency")
        require_non_empty_str(purpose, "purpose")
        self._check_instrument(payer_zid, instrument_id)
        payment_id = "PAY-" + new_id()
        now = self._clock.now()
        state = STATE_CREATED if escrow else STATE_RELEASED
        auto_at = add_business_days(now, auto_release_business_days) if escrow else now
        with self._db.transaction() as cursor:
            cursor.execute("INSERT INTO payments (payment_id, payer_zid, payee_zid, amount, currency, receive_currency, receive_amount, conversion_id, corridor, fee_send, instrument_id, purpose, hold_ref, state, auto_release_at, dispute_reason, dispute_opened_at, created_at, updated_at) VALUES (?, ?, ?, ?, ?, ?, NULL, NULL, NULL, NULL, ?, ?, NULL, ?, ?, NULL, NULL, ?, ?)", (payment_id, payer_zid, payee_zid, str(amt), currency.upper(), currency.upper(), instrument_id, purpose, state, auto_at, now, now))
        self._audit.append(event_type=EVENT_PAYMENT_CREATED, actor=payer_zid, subject=payment_id, payload={"amount": str(amt), "currency": currency.upper(), "escrow": escrow})
        self._emit(EVENT_PAYMENT_CREATED, payment_id, {"payer": payer_zid, "payee": payee_zid, "amount": str(amt), "currency": currency.upper(), "escrow": escrow})
        if not escrow:
            self._emit(EVENT_PAYMENT_RELEASED, payment_id, {"instant": True})
        return self.get_payment(payment_id)

    def send_money(self, *, payer_zid: str, payee_zid: str, amount, currency: str, instrument_id: str, receive_currency: str = "", escrow: bool = False, note: str = "") -> dict:
        """Envio de dinero (remesa). Cruza monedas via CurrencyEngine."""
        amt = amount if isinstance(amount, Decimal) else Decimal(str(amount))
        cur = currency.upper().strip()
        recv = (receive_currency or cur).upper().strip()
        corridor = "DOMESTIC" if recv == cur else "INTERNATIONAL"
        sched = FEE_SCHEDULE[corridor]
        conv_id = None
        recv_amt = str(amt)
        if corridor == "INTERNATIONAL":
            conv = self.convert_for_payment(requester_zid=payer_zid, base=cur, quote_ccy=recv, amount=amt)
            conv_id = conv["conversion_id"]
            recv_amt = conv["quote_amount"]
        fee_send = self._flat_in(cur, payer_zid, sched["flat_usd"]) + amt * sched["pct"]
        pay = self.create_payment(payer_zid=payer_zid, payee_zid=payee_zid, amount=amt, currency=cur, instrument_id=instrument_id, purpose="money_transfer", escrow=escrow)
        self._db.execute("UPDATE payments SET receive_currency = ?, receive_amount = ?, conversion_id = ?, corridor = ?, fee_send = ? WHERE payment_id = ?", (recv, recv_amt, conv_id, corridor, str(fee_send), pay["payment_id"]))
        self._audit.append(event_type=EVENT_REMITTANCE_ROUTED, actor=payer_zid, subject=pay["payment_id"], payload={"corridor": corridor, "send": cur, "receive": recv, "fee_send": str(fee_send), "conversion_id": conv_id})
        self._emit(EVENT_REMITTANCE_ROUTED, pay["payment_id"], {"corridor": corridor, "send_currency": cur, "receive_currency": recv, "receive_amount": recv_amt, "conversion_id": conv_id})
        return self.get_payment(pay["payment_id"])

    def pay_service(self, *, payer_zid: str, service_type: str, service_account: str, amount, currency: str, instrument_id: str, provider_zid: str = "", reference: str = "") -> dict:
        """Paga factura de servicio basico. Directo, sin escrow."""
        if service_type not in SERVICE_TYPES:
            raise ValidationError("unknown service type: " + service_type)
        require_non_empty_str(service_account, "service_account")
        amt = amount if isinstance(amount, Decimal) else Decimal(str(amount))
        cur = currency.upper()
        sched = FEE_SCHEDULE["SERVICE"]
        fee_send = self._flat_in(cur, payer_zid, sched["flat_usd"]) + amt * sched["pct"]
        payee = provider_zid or ("SVC://" + service_type)
        pay = self.create_payment(payer_zid=payer_zid, payee_zid=payee, amount=amt, currency=cur, instrument_id=instrument_id, purpose="service:" + service_type + ":" + service_account, escrow=False)
        self._db.execute("UPDATE payments SET fee_send = ? WHERE payment_id = ?", (str(fee_send), pay["payment_id"]))
        self._audit.append(event_type="payments.service.paid", actor=payer_zid, subject=pay["payment_id"], payload={"service_type": service_type, "service_account": service_account, "reference": reference, "fee_send": str(fee_send)})
        pay = self.get_payment(pay["payment_id"])
        pay["service_type"] = service_type
        pay["service_account"] = service_account
        return pay

    def marketplace_fees(self, *, sale_amount, with_shipping_label: bool = True) -> dict:
        """Comisiones SUBASTAS/marke: % comprador + % vendedor + etiqueta."""
        amt = sale_amount if isinstance(sale_amount, Decimal) else Decimal(str(sale_amount))
        buyer = amt * MARKETPLACE_FEES["buyer_pct"]
        seller = amt * MARKETPLACE_FEES["seller_pct"]
        ship = MARKETPLACE_FEES["shipping_label_fee_usd"] if with_shipping_label else Decimal("0")
        return {"sale_amount": str(amt), "buyer_fee": str(buyer), "seller_fee": str(seller), "shipping_label_fee": str(ship), "buyer_total": str(amt + buyer), "seller_net": str(amt - seller - ship)}

    def mark_held(self, payment_id: str, *, hold_ref: str) -> dict:
        require_non_empty_str(hold_ref, "hold_ref")
        return self._transition(payment_id, from_state=STATE_CREATED, to_state=STATE_HELD, extra_sql=", hold_ref = ?", extra_params=(hold_ref,), event_type=EVENT_PAYMENT_HELD, audit_payload={"hold_ref": hold_ref})

    def open_dispute(self, payment_id: str, *, reason: str) -> dict:
        require_non_empty_str(reason, "reason")
        row = self._db.query_one("SELECT * FROM payments WHERE payment_id = ?", (payment_id,))
        if row is None:
            raise UnknownPaymentError("unknown payment: " + payment_id)
        if str(row["state"]) != STATE_HELD:
            raise PaymentStateError("dispute requires HELD, got " + str(row["state"]))
        if self._clock.now() > float(row["auto_release_at"]):
            raise DisputeWindowClosedError("dispute window closed (3 business days)")
        now = self._clock.now()
        with self._db.transaction() as cursor:
            cursor.execute("UPDATE payments SET state = ?, dispute_reason = ?, dispute_opened_at = ?, updated_at = ? WHERE payment_id = ? AND state = ?", (STATE_DISPUTE, reason, now, now, payment_id, STATE_HELD))
        self._audit.append(event_type=EVENT_PAYMENT_DISPUTED, actor=str(row["payer_zid"]), subject=payment_id, payload={"reason": reason})
        self._emit(EVENT_PAYMENT_DISPUTED, payment_id, {"reason": reason})
        return self.get_payment(payment_id)

    def resolve_dispute(self, payment_id: str, *, outcome: str, note: str = "") -> dict:
        if outcome not in ("release", "refund"):
            raise ValidationError("outcome must be release|refund")
        final = STATE_RELEASED if outcome == "release" else STATE_REFUNDED
        ev = EVENT_PAYMENT_RELEASED if outcome == "release" else EVENT_PAYMENT_REFUNDED
        return self._transition(payment_id, from_state=STATE_DISPUTE, to_state=final, event_type=ev, audit_payload={"note": note})

    def release(self, payment_id: str) -> dict:
        return self._transition(payment_id, from_state=STATE_HELD, to_state=STATE_RELEASED, event_type=EVENT_PAYMENT_RELEASED, audit_payload={"manual": True})

    def auto_release_due(self) -> list:
        now = self._clock.now()
        rows = self._db.query_all("SELECT payment_id FROM payments WHERE state = ? AND auto_release_at <= ?", (STATE_HELD, now))
        released = []
        for r in rows:
            try:
                self.release(str(r["payment_id"]))
                released.append(str(r["payment_id"]))
            except PaymentStateError:
                continue
        return released

    def get_payment(self, payment_id: str) -> dict:
        row = self._db.query_one("SELECT * FROM payments WHERE payment_id = ?", (payment_id,))
        if row is None:
            raise UnknownPaymentError("unknown payment: " + payment_id)
        return {"payment_id": str(row["payment_id"]), "payer_zid": str(row["payer_zid"]), "payee_zid": str(row["payee_zid"]), "amount": str(row["amount"]), "currency": str(row["currency"]), "receive_currency": str(row["receive_currency"] or ""), "receive_amount": str(row["receive_amount"]) if row["receive_amount"] else None, "conversion_id": str(row["conversion_id"]) if row["conversion_id"] else None, "corridor": str(row["corridor"]) if row["corridor"] else None, "fee_send": str(row["fee_send"]) if row["fee_send"] else None, "instrument_id": str(row["instrument_id"]), "purpose": str(row["purpose"]), "hold_ref": str(row["hold_ref"]) if row["hold_ref"] else None, "state": str(row["state"]), "auto_release_at": float(row["auto_release_at"]), "dispute_reason": str(row["dispute_reason"]) if row["dispute_reason"] else None, "created_at": float(row["created_at"]), "updated_at": float(row["updated_at"])}

    def list_payments(self, *, zid: str) -> tuple:
        rows = self._db.query_all("SELECT * FROM payments WHERE payer_zid = ? OR payee_zid = ? ORDER BY created_at DESC LIMIT 200", (zid, zid))
        return tuple({"payment_id": str(r["payment_id"]), "payer_zid": str(r["payer_zid"]), "payee_zid": str(r["payee_zid"]), "amount": str(r["amount"]), "currency": str(r["currency"]), "receive_currency": str(r["receive_currency"] or ""), "corridor": str(r["corridor"]) if r["corridor"] else None, "state": str(r["state"]), "purpose": str(r["purpose"])} for r in rows)

    def convert_for_payment(self, *, requester_zid: str, base: str, quote_ccy: str, amount) -> dict:
        if self._currency is None:
            raise PaymentStateError("currency engine not wired")
        if not isinstance(amount, Decimal):
            amount = Decimal(str(amount))
        signed, conversion_id, exact = self._currency.convert(subject_zid=requester_zid, base=base, quote_ccy=quote_ccy, amount=amount)
        return {"conversion_id": conversion_id, "rate": str(signed.quote.rate), "quote_amount": str(exact), "source": signed.quote.source}

    def register_phone_alias(self, *, zid: str, phone: str) -> dict:
        require_non_empty_str(zid, "zid")
        p = _norm_phone(phone)
        now = self._clock.now()
        with self._db.transaction() as cursor:
            cursor.execute("INSERT INTO phone_aliases (phone, zid, verified, created_at) VALUES (?, ?, 0, ?) ON CONFLICT(phone) DO UPDATE SET zid = excluded.zid, verified = 0", (p, zid, now))
        self._audit.append(event_type="payments.phone.alias_registered", actor=zid, subject=p, payload={})
        return {"phone": p, "zid": zid, "verified": False}

    def resolve_phone(self, phone: str):
        p = _norm_phone(phone)
        row = self._db.query_one("SELECT * FROM phone_aliases WHERE phone = ?", (p,))
        if row is None:
            return None
        return {"phone": p, "zid": str(row["zid"]), "verified": bool(row["verified"])}

    def pay_by_phone(self, *, payer_zid: str, phone: str, amount, currency: str, instrument_id: str, purpose: str = "money_transfer", escrow: bool = False) -> dict:
        res = self.resolve_phone(phone)
        if res is None:
            raise ValidationError("phone not registered in the network")
        return self.create_payment(payer_zid=payer_zid, payee_zid=res["zid"], amount=amount, currency=currency, instrument_id=instrument_id, purpose=purpose, escrow=escrow)

    def generate_payment_qr(self, *, payee_zid: str, purpose: str, amount=None, currency: str = "", expires_seconds: float = 900.0) -> dict:
        require_non_empty_str(payee_zid, "payee_zid")
        require_non_empty_str(purpose, "purpose")
        token = "QR-" + new_id()
        now = self._clock.now()
        exp = now + expires_seconds
        with self._db.transaction() as cursor:
            cursor.execute("INSERT INTO payment_requests (qr_token, payee_zid, amount, currency, purpose, expires_at, used_by_payment, created_at) VALUES (?, ?, ?, ?, ?, ?, NULL, ?)", (token, payee_zid, str(amount) if amount is not None else None, currency.upper() if currency else None, purpose, exp, now))
        self._audit.append(event_type=EVENT_QR_GENERATED, actor=payee_zid, subject=token, payload={})
        payload = {"v": 1, "net": "zyra", "tok": token, "to": payee_zid, "purpose": purpose}
        if amount is not None:
            payload["amt"] = str(amount)
            payload["ccy"] = currency.upper() if currency else ""
        payload_b64 = base64.b64encode(canonical_json_dumps(payload).encode("utf-8")).decode("ascii")
        return {"qr_token": token, "payload_b64": payload_b64, "expires_at": exp, "payee_zid": payee_zid}

    def pay_by_code(self, *, payer_zid: str, code: str, instrument_id: str, amount=None, currency: str = "") -> dict:
        require_non_empty_str(code, "code")
        token = code.strip()
        if not token.startswith("QR-"):
            try:
                decoded = base64.b64decode(token.encode("ascii")).decode("utf-8")
                import json as _j
                doc = _j.loads(decoded)
                token = str(doc.get("tok", ""))
            except Exception as exc:
                raise ValidationError("code is not a valid zyra QR/barcode") from exc
            if not token:
                raise ValidationError("code has no token")
        row = self._db.query_one("SELECT * FROM payment_requests WHERE qr_token = ?", (token,))
        if row is None:
            raise QRRequestUnavailableError("unknown payment request")
        if row["used_by_payment"]:
            raise QRRequestUnavailableError("payment request already used")
        if self._clock.now() > float(row["expires_at"]):
            raise QRRequestUnavailableError("payment request expired")
        qr_amount = row["amount"]
        final_amount = Decimal(str(qr_amount)) if qr_amount else (amount if isinstance(amount, Decimal) else Decimal(str(amount or "0")))
        if final_amount <= 0:
            raise ValidationError("amount required for open request")
        final_ccy = str(row["currency"]) if row["currency"] else (currency or "USD")
        pay = self.create_payment(payer_zid=payer_zid, payee_zid=str(row["payee_zid"]), amount=final_amount, currency=final_ccy, instrument_id=instrument_id, purpose="qr:" + str(row["purpose"]), escrow=False)
        self._db.execute("UPDATE payment_requests SET used_by_payment = ? WHERE qr_token = ?", (pay["payment_id"], token))
        pay["qr_token"] = token
        return pay

    def _transition(self, payment_id, *, from_state, to_state, extra_sql="", extra_params=(), event_type=None, audit_payload=None) -> dict:
        row = self._db.query_one("SELECT * FROM payments WHERE payment_id = ?", (payment_id,))
        if row is None:
            raise UnknownPaymentError("unknown payment: " + payment_id)
        if str(row["state"]) != from_state:
            raise PaymentStateError("payment " + payment_id + " is " + str(row["state"]) + ", expected " + from_state)
        now = self._clock.now()
        with self._db.transaction() as cursor:
            cursor.execute("UPDATE payments SET state = ?, updated_at = ?" + extra_sql + " WHERE payment_id = ? AND state = ?", (to_state, now) + tuple(extra_params) + (payment_id, from_state))
        self._audit.append(event_type=event_type or "payments.payment.updated", actor=str(row["payer_zid"]), subject=payment_id, payload=audit_payload or {})
        if event_type:
            self._emit(event_type, payment_id, {"from": from_state, "to": to_state, **(audit_payload or {})})
        return self.get_payment(payment_id)
