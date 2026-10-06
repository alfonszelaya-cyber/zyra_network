
"""Accounts Receivable Engine - cuentas por cobrar
(NG4). Facturas, abonos, aging, mora. Decimal 2d."""
from __future__ import annotations
from typing import List, Optional
import uuid
from shared_engines.common.clocks import Clock
from shared_engines.storage.database import Database
from shared_engines.storage.migrations import (
    Migration, MigrationRunner)

_MIGRATIONS = (
    Migration(1, "nexo_ar_invoices", (
        "CREATE TABLE IF NOT EXISTS nexo_ar_invoices (invoice_id TEXT PRIMARY KEY, company_id TEXT NOT NULL, client_id TEXT NOT NULL, invoice_number TEXT NOT NULL, amount TEXT NOT NULL, paid TEXT NOT NULL DEFAULT '0', currency TEXT NOT NULL DEFAULT 'USD', issued_at REAL NOT NULL, due_at REAL NOT NULL, status TEXT NOT NULL DEFAULT 'OPEN')",
    )),
    Migration(2, "nexo_ar_payments", (
        "CREATE TABLE IF NOT EXISTS nexo_ar_payments (payment_id TEXT PRIMARY KEY, invoice_id TEXT NOT NULL, amount TEXT NOT NULL, paid_at REAL NOT NULL, reference TEXT NOT NULL DEFAULT '')",
    )),
)

class AccountsReceivableEngine:
    """CxC: facturas, abonos, aging, mora."""

    def __init__(self, db, clock):
        self._db = db
        self._clock = clock
        MigrationRunner(db, "nexo.ar",
                        _MIGRATIONS).run(clock)

    def create_invoice(self, *, company_id, client_id,
                       invoice_number, amount,
                       credit_days=30,
                       currency="USD") -> dict:
        from decimal import Decimal as _D
        val = _D(str(amount))
        if val <= 0:
            raise ValueError(
                "monto positivo requerido")
        iid = "AR-" + str(uuid.uuid4())
        now = self._clock.now()
        due = now + (int(credit_days) * 86400)
        with self._db.transaction() as cursor:
            cursor.execute(
                "INSERT INTO nexo_ar_invoices"
                " (invoice_id, company_id,"
                " client_id, invoice_number,"
                " amount, paid, currency, issued_at,"
                " due_at, status)"
                " VALUES (?, ?, ?, ?, ?, '0', ?, ?,"
                " ?, 'OPEN')",
                (iid, company_id, client_id,
                 invoice_number, str(val), currency,
                 now, due))
        return {"invoice_id": iid,
                "company_id": company_id,
                "client_id": client_id,
                "invoice_number": invoice_number,
                "amount": str(val),
                "paid": "0",
                "balance": str(val),
                "due_at": due,
                "status": "OPEN"}

    def get_invoice(self,
                    invoice_id) -> Optional[dict]:
        row = self._db.query_one(
            "SELECT * FROM nexo_ar_invoices WHERE"
            " invoice_id = ?", (invoice_id,))
        return self._row(row) if row else None

    def _row(self, r) -> dict:
        from decimal import Decimal as _D
        amt = _D(str(r["amount"]))
        paid = _D(str(r["paid"]))
        return {"invoice_id": str(r["invoice_id"]),
                "company_id": str(r["company_id"]),
                "client_id": str(r["client_id"]),
                "invoice_number":
                    str(r["invoice_number"]),
                "amount": str(amt),
                "paid": str(paid),
                "balance": str(amt - paid),
                "currency": str(r["currency"]),
                "due_at": float(r["due_at"]),
                "status": str(r["status"])}

    def register_payment(self, *, invoice_id,
                         amount,
                         reference="") -> dict:
        from decimal import Decimal as _D
        inv = self.get_invoice(invoice_id)
        if not inv:
            raise KeyError(invoice_id)
        pay = _D(str(amount))
        if pay <= 0:
            raise ValueError("abono positivo")
        bal = _D(inv["balance"])
        if pay > bal:
            raise ValueError(
                "abono mayor que saldo")
        now = self._clock.now()
        new_paid = _D(inv["paid"]) + pay
        status = ("PAID"
                  if new_paid == _D(inv["amount"])
                  else "PARTIAL")
        with self._db.transaction() as cursor:
            cursor.execute(
                "INSERT INTO nexo_ar_payments"
                " (payment_id, invoice_id, amount,"
                " paid_at, reference)"
                " VALUES (?, ?, ?, ?, ?)",
                ("ARP-" + str(uuid.uuid4()),
                 invoice_id, str(pay), now,
                 reference))
            cursor.execute(
                "UPDATE nexo_ar_invoices SET"
                " paid = ?, status = ? WHERE"
                " invoice_id = ?",
                (str(new_paid), status,
                 invoice_id))
        return {"invoice_id": invoice_id,
                "paid": str(new_paid),
                "balance": str(
                    _D(inv["amount"])
                    - new_paid),
                "status": status}

    def aging(self, company_id) -> dict:
        from decimal import Decimal as _D
        now = self._clock.now()
        rows = self._db.query_all(
            "SELECT amount, paid, due_at FROM"
            " nexo_ar_invoices WHERE company_id = ?"
            " AND status != 'PAID'",
            (company_id,))
        b = {"current": _D("0"),
             "1-30": _D("0"),
             "31-60": _D("0"),
             "60+": _D("0")}
        overdue = 0
        for r in rows:
            bal = (_D(str(r["amount"]))
                   - _D(str(r["paid"])))
            days = int((now
                        - float(r["due_at"]))
                       / 86400)
            if days <= 0:
                key = "current"
            elif days <= 30:
                key = "1-30"
                overdue = overdue + 1
            elif days <= 60:
                key = "31-60"
                overdue = overdue + 1
            else:
                key = "60+"
                overdue = overdue + 1
            b[key] = b[key] + bal
        buckets = {k: str(v)
                   for k, v in b.items()}
        total = sum(b.values(), _D("0"))
        return {"company_id": company_id,
                "aging": buckets,
                "total_open": str(total),
                "overdue_invoices": overdue}

    def open_invoices(self, company_id) -> List[dict]:
        rows = self._db.query_all(
            "SELECT * FROM nexo_ar_invoices WHERE"
            " company_id = ? AND status != 'PAID'"
            " ORDER BY due_at", (company_id,))
        return [self._row(r) for r in rows]
