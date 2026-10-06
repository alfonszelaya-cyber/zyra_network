
"""Finance Engine - registros financieros centrales
(NG4). Ingresos, gastos, ajustes, provisiones."""
from __future__ import annotations
from typing import List, Optional
import uuid
from shared_engines.common.clocks import Clock
from shared_engines.storage.database import Database
from shared_engines.storage.migrations import (
    Migration, MigrationRunner)

RECORD_TYPES = ("INCOME", "EXPENSE", "ADJUSTMENT",
                "PROVISION")

_MIGRATIONS = (
    Migration(1, "nexo_finance_records", (
        "CREATE TABLE IF NOT EXISTS nexo_finance_records (record_id TEXT PRIMARY KEY, company_id TEXT NOT NULL, period TEXT NOT NULL, record_type TEXT NOT NULL, category TEXT NOT NULL DEFAULT '', amount TEXT NOT NULL, currency TEXT NOT NULL DEFAULT 'USD', description TEXT NOT NULL DEFAULT '', created_at REAL NOT NULL)",
    )),
)

class FinanceEngine:
    """Registros financieros del periodo (Decimal)."""

    def __init__(self, db, clock):
        self._db = db
        self._clock = clock
        MigrationRunner(db, "nexo.finrecords",
                        _MIGRATIONS).run(clock)

    def create_record(self, *, company_id, period,
                      record_type, amount,
                      category="", currency="USD",
                      description="") -> dict:
        from decimal import Decimal as _D
        val = _D(str(amount))
        if record_type not in RECORD_TYPES:
            record_type = "ADJUSTMENT"
        rid = "FIN-" + str(uuid.uuid4())
        now = self._clock.now()
        with self._db.transaction() as cursor:
            cursor.execute(
                "INSERT INTO nexo_finance_records"
                " (record_id, company_id, period,"
                " record_type, category, amount,"
                " currency, description, created_at)"
                " VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)",
                (rid, company_id, period,
                 record_type, category, str(val),
                 currency, description, now))
        return {"record_id": rid,
                "company_id": company_id,
                "period": period,
                "record_type": record_type,
                "category": category,
                "amount": str(val),
                "currency": currency}

    def records_of(self, company_id,
                   period="") -> List[dict]:
        if period:
            rows = self._db.query_all(
                "SELECT * FROM"
                " nexo_finance_records WHERE"
                " company_id = ? AND period = ?"
                " ORDER BY created_at",
                (company_id, period))
        else:
            rows = self._db.query_all(
                "SELECT * FROM"
                " nexo_finance_records WHERE"
                " company_id = ?"
                " ORDER BY created_at",
                (company_id,))
        return [{"record_id": str(r["record_id"]),
                 "period": str(r["period"]),
                 "record_type":
                     str(r["record_type"]),
                 "category": str(r["category"]),
                 "amount": str(r["amount"]),
                 "currency": str(r["currency"])}
                for r in rows]

    def totals(self, company_id, period) -> dict:
        from decimal import Decimal as _D
        rows = self._db.query_all(
            "SELECT record_type, amount FROM"
            " nexo_finance_records WHERE"
            " company_id = ? AND period = ?",
            (company_id, period))
        ing = _D("0")
        gas = _D("0")
        for r in rows:
            if str(r["record_type"]) == "INCOME":
                ing = ing + _D(str(r["amount"]))
            elif str(r["record_type"]) == "EXPENSE":
                gas = gas + _D(str(r["amount"]))
        return {"period": period,
                "income": str(ing),
                "expense": str(gas),
                "net": str(ing - gas)}
