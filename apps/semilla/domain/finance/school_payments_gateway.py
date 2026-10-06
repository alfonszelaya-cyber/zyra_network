
"""School Payments Gateway - pagos escolares (SM3).
SE-4: cobro REAL via PaymentsEngine de la Red
(inyectado); sin engine: not_configured honesto."""
from __future__ import annotations
from decimal import (Decimal as _D,
                     ROUND_HALF_UP as _UP)
from typing import List, Optional
import json as _j
import uuid
from shared_engines.common.clocks import Clock
from shared_engines.storage.database import (
    Database)
from shared_engines.storage.migrations import (
    Migration, MigrationRunner)

_Q = "0.01"
FEE_TYPES = ("MATRICULA", "MENSUALIDAD",
             "UNIFORME", "MATERIALES",
             "TRANSPORTE", "CAFETERIA", "OTRO")

_MIGRATIONS = (
    Migration(1, "sm_school_payments", (
        "CREATE TABLE IF NOT EXISTS sm_school_payments (payment_id TEXT PRIMARY KEY, student_id TEXT NOT NULL, fee_type TEXT NOT NULL, amount TEXT NOT NULL, currency TEXT NOT NULL DEFAULT 'USD', status TEXT NOT NULL DEFAULT 'REGISTERED', network_result_json TEXT NOT NULL DEFAULT '{}', created_at REAL NOT NULL)",
    )),
)

class SchoolPaymentsGateway:
    """Pagos escolares via Red (SE-4)."""

    def __init__(self, db, clock,
                 payments_engine=None):
        self._db = db
        self._clock = clock
        self._engine = payments_engine
        MigrationRunner(db, "sm.paygw",
                        _MIGRATIONS).run(clock)

    @property
    def mode(self) -> str:
        return ("red_payments"
                if self._engine is not None
                else "not_configured")

    def pay(self, *, payer_zid, payee_zid,
            student_id, fee_type, amount,
            currency="USD", instrument_id="",
            reference="") -> dict:
        if fee_type not in FEE_TYPES:
            raise ValueError(
                "fee_type invalido: "
                + str(fee_type))
        amt = _D(str(amount)).quantize(
            _D(_Q), rounding=_UP)
        if amt <= 0:
            raise ValueError(
                "amount positivo requerido")
        if self._engine is None:
            return {"status":
                        "not_configured",
                    "reason": "PaymentsEngine de"
                              " la Red no inyectado"}
        try:
            net = self._engine.send_money(
                payer_zid=str(payer_zid),
                payee_zid=str(payee_zid),
                amount=amt, currency=currency,
                instrument_id=str(instrument_id),
                note=("SCHOOL_FEE:"
                      + str(fee_type) + ":"
                      + str(student_id) + ":"
                      + str(reference)))
        except Exception as e:
            net = {"error": str(e)[:200]}
        pid = "SMPAY-" + str(uuid.uuid4())
        now = self._clock.now()
        with self._db.transaction() as cursor:
            cursor.execute(
                "INSERT INTO"
                " sm_school_payments"
                " (payment_id, student_id,"
                " fee_type, amount, currency,"
                " status, network_result_json,"
                " created_at)"
                " VALUES (?, ?, ?, ?, ?,"
                " 'REGISTERED', ?, ?)",
                (pid, student_id, fee_type,
                 str(amt), currency,
                 _j.dumps(net, default=str),
                 now))
        return {"payment_id": pid,
                "student_id": student_id,
                "fee_type": fee_type,
                "amount": str(amt),
                "currency": currency,
                "status": "REGISTERED",
                "network": net}

    def payments_of(self, student_id
                    ) -> List[dict]:
        rows = self._db.query_all(
            "SELECT * FROM sm_school_payments"
            " WHERE student_id = ? ORDER BY"
            " created_at", (student_id,))
        return [{"payment_id":
                     str(r["payment_id"]),
                 "fee_type": str(r["fee_type"]),
                 "amount": str(r["amount"]),
                 "currency": str(r["currency"]),
                 "status": str(r["status"])}
                for r in rows]

    def total_paid(self, student_id) -> str:
        rows = self._db.query_all(
            "SELECT amount FROM"
            " sm_school_payments WHERE"
            " student_id = ? AND status ="
            " 'REGISTERED'", (student_id,))
        total = _D("0")
        for r in rows:
            total = total + _D(str(r["amount"]))
        return str(total.quantize(_D(_Q)))
