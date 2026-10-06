
"""Motor de pagos de dominio NEXO (capa contable fina).

Regla 69: el motor transversal vive en
shared_engines.payments; NEXO NO lo duplica — lo
consume por inyeccion (opcional) y su trabajo contable
es registrar el impacto de cada pago + emitir eventos
NEXO_*. Montos Decimal (regla 61)."""
from __future__ import annotations
from typing import List, Optional
import uuid
from shared_engines.common.clocks import Clock
from shared_engines.storage.database import Database
from shared_engines.storage.migrations import (
    Migration, MigrationRunner)

DIRECTIONS = ("INCOMING", "OUTGOING")

_MIGRATIONS = (
    Migration(1, "nexo_payments", (
        "CREATE TABLE IF NOT EXISTS nexo_payments (payment_id TEXT PRIMARY KEY, company_id TEXT NOT NULL, direction TEXT NOT NULL, amount TEXT NOT NULL, currency TEXT NOT NULL DEFAULT 'USD', counterparty TEXT NOT NULL DEFAULT '', method TEXT NOT NULL DEFAULT '', reference TEXT NOT NULL DEFAULT '', status TEXT NOT NULL DEFAULT 'RECORDED', created_at REAL NOT NULL)",
    )),
)

class NexoPaymentEngine:
    """Registro contable de pagos + eventos NEXO_*."""

    def __init__(self, db, clock,
                 payments_engine=None, bus=None):
        self._db = db
        self._clock = clock
        self._shared = payments_engine
        self._bus = bus
        MigrationRunner(db, "nexo.payments",
                        _MIGRATIONS).run(clock)

    def _emit(self, event_name, company_id, payload):
        if self._bus is None:
            return None
        try:
            from apps.nexo.events.contracts import (
                make_event)
            ev = make_event(
                event_name, company_id=company_id,
                payload=payload,
                occurred_at=self._clock.now())
            return self._bus.publish(ev)
        except Exception:
            return None

    def record_payment(self, *, company_id, direction,
                       amount, currency="USD",
                       counterparty="", method="",
                       reference="") -> dict:
        from decimal import Decimal as _D
        val = _D(str(amount))
        if val <= 0:
            raise ValueError(
                "monto debe ser positivo")
        if direction not in DIRECTIONS:
            direction = "INCOMING"
        pid = "PAY-" + str(uuid.uuid4())
        now = self._clock.now()
        with self._db.transaction() as cursor:
            cursor.execute(
                "INSERT INTO nexo_payments"
                " (payment_id, company_id, direction,"
                " amount, currency, counterparty,"
                " method, reference, status,"
                " created_at)"
                " VALUES (?, ?, ?, ?, ?, ?, ?, ?,"
                " 'RECORDED', ?)",
                (pid, company_id, direction, str(val),
                 currency, counterparty, method,
                 reference, now))
        event = ("NEXO_PAYMENT_RECEIVED"
                 if direction == "INCOMING"
                 else "NEXO_PAYMENT_SENT")
        pub = self._emit(event, company_id,
                         {"payment_id": pid,
                          "amount": str(val),
                          "currency": currency,
                          "reference": reference})
        return {"payment_id": pid,
                "company_id": company_id,
                "direction": direction,
                "amount": str(val),
                "currency": currency,
                "status": "RECORDED",
                "event_published": bool(
                    pub and pub.get("event_id"))}

    def get_payment(self, payment_id) -> Optional[dict]:
        row = self._db.query_one(
            "SELECT * FROM nexo_payments"
            " WHERE payment_id = ?", (payment_id,))
        return self._row(row) if row else None

    def _row(self, r) -> dict:
        return {"payment_id": str(r["payment_id"]),
                "company_id": str(r["company_id"]),
                "direction": str(r["direction"]),
                "amount": str(r["amount"]),
                "currency": str(r["currency"]),
                "counterparty": str(r["counterparty"]),
                "method": str(r["method"]),
                "reference": str(r["reference"]),
                "status": str(r["status"]),
                "created_at": float(r["created_at"])}

    def payments_for(self, company_id) -> List[dict]:
        rows = self._db.query_all(
            "SELECT * FROM nexo_payments"
            " WHERE company_id = ?"
            " ORDER BY created_at", (company_id,))
        return [self._row(r) for r in rows]

    def mark_reconciled(self, payment_id) -> dict:
        self._db.execute(
            "UPDATE nexo_payments SET"
            " status = 'RECONCILED'"
            " WHERE payment_id = ?", (payment_id,))
        return self.get_payment(payment_id)
