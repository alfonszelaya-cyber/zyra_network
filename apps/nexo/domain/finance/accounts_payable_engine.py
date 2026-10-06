
"""Accounts Payable Engine - cuentas por pagar (NG4).
Aprobacion obligatoria, pagos parciales. Decimal 2d."""
from __future__ import annotations
from typing import List, Optional
import uuid
from shared_engines.common.clocks import Clock
from shared_engines.storage.database import Database
from shared_engines.storage.migrations import (
    Migration, MigrationRunner)

_MIGRATIONS = (
    Migration(1, "nexo_ap_invoices", (
        "CREATE TABLE IF NOT EXISTS nexo_ap_invoices (invoice_id TEXT PRIMARY KEY, company_id TEXT NOT NULL, supplier_id TEXT NOT NULL, invoice_number TEXT NOT NULL, purchase_order TEXT NOT NULL DEFAULT '', amount TEXT NOT NULL, paid TEXT NOT NULL DEFAULT '0', currency TEXT NOT NULL DEFAULT 'USD', approved_by TEXT, status TEXT NOT NULL DEFAULT 'PENDING_APPROVAL', issued_at REAL NOT NULL)",
    )),
)

class AccountsPayableEngine:
    """CxP: facturas proveedor, OC, aprobacion, pagos."""

    def __init__(self, db, clock):
        self._db = db
        self._clock = clock
        MigrationRunner(db, "nexo.ap",
                        _MIGRATIONS).run(clock)

    def create_invoice(self, *, company_id,
                       supplier_id, invoice_number,
                       amount, purchase_order="",
                       currency="USD") -> dict:
        from decimal import Decimal as _D
        val = _D(str(amount))
        if val <= 0:
            raise ValueError(
                "monto positivo requerido")
        iid = "AP-" + str(uuid.uuid4())
        now = self._clock.now()
        with self._db.transaction() as cursor:
            cursor.execute(
                "INSERT INTO nexo_ap_invoices"
                " (invoice_id, company_id,"
                " supplier_id, invoice_number,"
                " purchase_order, amount, paid,"
                " currency, approved_by, status,"
                " issued_at)"
                " VALUES (?, ?, ?, ?, ?, ?, '0', ?,"
                " NULL, 'PENDING_APPROVAL', ?)",
                (iid, company_id, supplier_id,
                 invoice_number, purchase_order,
                 str(val), currency, now))
        return {"invoice_id": iid,
                "amount": str(val),
                "status": "PENDING_APPROVAL"}

    def approve_invoice(self, *, invoice_id,
                        approver) -> dict:
        row = self._db.query_one(
            "SELECT status FROM nexo_ap_invoices"
            " WHERE invoice_id = ?", (invoice_id,))
        if not row:
            raise KeyError(invoice_id)
        if str(row["status"]) != "PENDING_APPROVAL":
            raise ValueError(
                "solo PENDING_APPROVAL se aprueba")
        self._db.execute(
            "UPDATE nexo_ap_invoices SET"
            " status = 'APPROVED', approved_by = ?"
            " WHERE invoice_id = ?",
            (approver, invoice_id))
        return self.get_invoice(invoice_id)

    def get_invoice(self,
                    invoice_id) -> Optional[dict]:
        from decimal import Decimal as _D
        row = self._db.query_one(
            "SELECT * FROM nexo_ap_invoices WHERE"
            " invoice_id = ?", (invoice_id,))
        if not row:
            return None
        amt = _D(str(row["amount"]))
        paid = _D(str(row["paid"]))
        return {"invoice_id":
                    str(row["invoice_id"]),
                "company_id":
                    str(row["company_id"]),
                "supplier_id":
                    str(row["supplier_id"]),
                "invoice_number":
                    str(row["invoice_number"]),
                "purchase_order":
                    str(row["purchase_order"]),
                "amount": str(amt),
                "paid": str(paid),
                "balance": str(amt - paid),
                "approved_by":
                    (str(row["approved_by"])
                     if row["approved_by"]
                     else None),
                "status": str(row["status"])}

    def register_payment(self, *, invoice_id,
                         amount) -> dict:
        from decimal import Decimal as _D
        inv = self.get_invoice(invoice_id)
        if not inv:
            raise KeyError(invoice_id)
        if inv["status"] not in ("APPROVED",
                                 "PARTIAL"):
            raise ValueError(
                "requiere factura aprobada")
        pay = _D(str(amount))
        if pay <= 0 or pay > _D(inv["balance"]):
            raise ValueError(
                "monto invalido vs saldo")
        new_paid = _D(inv["paid"]) + pay
        status = ("PAID"
                  if new_paid == _D(inv["amount"])
                  else "PARTIAL")
        self._db.execute(
            "UPDATE nexo_ap_invoices SET"
            " paid = ?, status = ? WHERE"
            " invoice_id = ?",
            (str(new_paid), status, invoice_id))
        return {"invoice_id": invoice_id,
                "paid": str(new_paid),
                "balance": str(
                    _D(inv["amount"])
                    - new_paid),
                "status": status}

    def pending_approval(self,
                         company_id) -> List[dict]:
        rows = self._db.query_all(
            "SELECT invoice_id, supplier_id,"
            " amount FROM nexo_ap_invoices WHERE"
            " company_id = ? AND"
            " status = 'PENDING_APPROVAL'",
            (company_id,))
        return [{"invoice_id":
                     str(r["invoice_id"]),
                 "supplier_id":
                     str(r["supplier_id"]),
                 "amount": str(r["amount"])}
                for r in rows]
