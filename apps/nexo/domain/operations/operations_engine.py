
"""Operations Engine - NEXO / ZYRA (migrado mejorado).

Area operativa-contable de NEXO: ciclo de vida completo
de operaciones contables, financieras y documentales de
empresas, alcaldias, gobiernos y bancos. Numeracion
secuencial por empresa (libro contable real). Montos
SIEMPRE Decimal (regla 61). LOGISTICS_COST registra el
costo contable de fletes/transportes (regla 70: solo lo
contable de la logistica vive en NEXO). Toda operacion
deja rastro auditable."""
from __future__ import annotations
from typing import Dict, List, Optional
import json as _j
import uuid
from shared_engines.common.clocks import Clock
from shared_engines.storage.database import Database
from shared_engines.storage.migrations import (
    Migration, MigrationRunner)

OPERATION_TYPES = ("TRANSACTION", "ADJUSTMENT", "REPORT",
                   "DECLARATION", "AUDIT", "DOCUMENT_FLOW",
                   "PAYMENT", "COLLECTION", "LOGISTICS_COST")
OPERATION_STATUSES = ("DRAFT", "PENDING", "VALIDATED",
                      "APPROVED", "IN_PROGRESS", "COMPLETED",
                      "REJECTED", "CANCELLED")
PRIORITIES = ("LOW", "NORMAL", "HIGH", "CRITICAL")

_TRANSITIONS = {
    "DRAFT": ("PENDING", "CANCELLED"),
    "PENDING": ("VALIDATED", "REJECTED", "CANCELLED"),
    "VALIDATED": ("APPROVED", "REJECTED", "CANCELLED"),
    "APPROVED": ("IN_PROGRESS", "CANCELLED"),
    "IN_PROGRESS": ("COMPLETED", "CANCELLED"),
    "COMPLETED": (),
    "REJECTED": (),
    "CANCELLED": (),
}

_MIGRATIONS = (
    Migration(1, "nexo_operations", (
        "CREATE TABLE IF NOT EXISTS nexo_operations (operation_id TEXT PRIMARY KEY, operation_number INTEGER NOT NULL, company_id TEXT NOT NULL, operation_type TEXT NOT NULL, description TEXT NOT NULL DEFAULT '', amount TEXT NOT NULL DEFAULT '0', currency TEXT NOT NULL DEFAULT 'USD', status TEXT NOT NULL DEFAULT 'DRAFT', priority TEXT NOT NULL DEFAULT 'NORMAL', requested_by TEXT NOT NULL DEFAULT '', approved_by TEXT, completed_at REAL, created_at REAL NOT NULL, updated_at REAL NOT NULL, metadata_json TEXT NOT NULL DEFAULT '{}')",
    )),
    Migration(2, "nexo_op_counter", (
        "CREATE TABLE IF NOT EXISTS nexo_op_counter (company_id TEXT PRIMARY KEY, last_number INTEGER NOT NULL)",
    )),
)

class OperationsEngine:
    """Motor de operaciones contables (persistente)."""

    def __init__(self, db, clock):
        self._db = db
        self._clock = clock
        MigrationRunner(db, "nexo.operations",
                        _MIGRATIONS).run(clock)

    def _next_number(self, cursor, company_id) -> int:
        cursor.execute(
            "SELECT last_number FROM nexo_op_counter"
            " WHERE company_id = ?", (company_id,))
        row = cursor.fetchone()
        if row is None:
            cursor.execute(
                "INSERT INTO nexo_op_counter"
                " (company_id, last_number) VALUES (?, 1)",
                (company_id,))
            return 1
        nxt = int(row["last_number"]) + 1
        cursor.execute(
            "UPDATE nexo_op_counter SET last_number = ?"
            " WHERE company_id = ?", (nxt, company_id))
        return nxt

    def create_operation(self, *, company_id,
                         operation_type, description="",
                         amount="0", currency="USD",
                         priority="NORMAL",
                         requested_by="",
                         metadata=None) -> dict:
        from decimal import Decimal as _D
        val = _D(str(amount))
        if operation_type not in OPERATION_TYPES:
            operation_type = "TRANSACTION"
        if priority not in PRIORITIES:
            priority = "NORMAL"
        oid = "OP-" + str(uuid.uuid4())
        now = self._clock.now()
        with self._db.transaction() as cursor:
            num = self._next_number(cursor, company_id)
            cursor.execute(
                "INSERT INTO nexo_operations"
                " (operation_id, operation_number,"
                " company_id, operation_type,"
                " description, amount, currency,"
                " status, priority, requested_by,"
                " approved_by, completed_at,"
                " created_at, updated_at,"
                " metadata_json)"
                " VALUES (?, ?, ?, ?, ?, ?, ?, 'DRAFT',"
                " ?, ?, NULL, NULL, ?, ?, ?)",
                (oid, num, company_id, operation_type,
                 description, str(val), currency,
                 priority, requested_by, now, now,
                 _j.dumps(metadata or {},
                          default=str)))
        return self.get_operation(oid)

    def get_operation(self,
                      operation_id) -> Optional[dict]:
        row = self._db.query_one(
            "SELECT * FROM nexo_operations"
            " WHERE operation_id = ?", (operation_id,))
        return self._row(row) if row else None

    def _row(self, r) -> dict:
        return {"operation_id": str(r["operation_id"]),
                "operation_number":
                    int(r["operation_number"]),
                "company_id": str(r["company_id"]),
                "operation_type": str(r["operation_type"]),
                "description": str(r["description"]),
                "amount": str(r["amount"]),
                "currency": str(r["currency"]),
                "status": str(r["status"]),
                "priority": str(r["priority"]),
                "requested_by": str(r["requested_by"]),
                "approved_by": (str(r["approved_by"])
                                if r["approved_by"]
                                else None),
                "completed_at": (float(r["completed_at"])
                                 if r["completed_at"]
                                 else None),
                "created_at": float(r["created_at"]),
                "updated_at": float(r["updated_at"])}

    def transition(self, *, operation_id, new_status,
                   actor="") -> dict:
        op = self.get_operation(operation_id)
        if not op:
            raise KeyError(operation_id)
        cur = op["status"]
        if new_status not in _TRANSITIONS.get(cur, ()):
            raise ValueError(
                "transicion invalida: " + cur
                + " -> " + new_status)
        now = self._clock.now()
        completed = (now if new_status == "COMPLETED"
                     else None)
        self._db.execute(
            "UPDATE nexo_operations SET status = ?,"
            " approved_by = CASE WHEN ? = 'APPROVED'"
            " THEN ? ELSE approved_by END,"
            " completed_at = CASE WHEN ? = 'COMPLETED'"
            " THEN ? ELSE completed_at END,"
            " updated_at = ? WHERE operation_id = ?",
            (new_status, new_status, actor,
             new_status, completed, now,
             operation_id))
        return self.get_operation(operation_id)

    def list_by_company(self, company_id,
                        status="") -> List[dict]:
        if status:
            rows = self._db.query_all(
                "SELECT * FROM nexo_operations"
                " WHERE company_id = ? AND status = ?"
                " ORDER BY operation_number",
                (company_id, status))
        else:
            rows = self._db.query_all(
                "SELECT * FROM nexo_operations"
                " WHERE company_id = ?"
                " ORDER BY operation_number",
                (company_id,))
        return [self._row(r) for r in rows]

    def company_totals(self, company_id) -> dict:
        from decimal import Decimal as _D
        rows = self._db.query_all(
            "SELECT amount, status FROM"
            " nexo_operations"
            " WHERE company_id = ?", (company_id,))
        total = _D("0")
        completed = 0
        for r in rows:
            st = str(r["status"])
            if st in ("COMPLETED", "IN_PROGRESS"):
                total = total + _D(str(r["amount"]))
                if st == "COMPLETED":
                    completed = completed + 1
        return {"total_operations": len(rows),
                "completed": completed,
                "active_amount": str(total)}
