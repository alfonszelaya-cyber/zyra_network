
"""Budget Engine - presupuestos (NG4). Presupuesto vs
real con alertas. Montos SIEMPRE cuantizados a 2
decimales AL LEER (SQLite puede devolver 550.0 en
TEXT; el engine normaliza a 550.00 — regla 61)."""
from __future__ import annotations
from typing import List, Optional
import uuid
from shared_engines.common.clocks import Clock
from shared_engines.storage.database import Database
from shared_engines.storage.migrations import (
    Migration, MigrationRunner)

_Q = "0.01"

_MIGRATIONS = (
    Migration(1, "nexo_budgets", (
        "CREATE TABLE IF NOT EXISTS nexo_budgets (budget_id TEXT PRIMARY KEY, company_id TEXT NOT NULL, period TEXT NOT NULL, category TEXT NOT NULL, budgeted TEXT NOT NULL, actual TEXT NOT NULL DEFAULT '0', currency TEXT NOT NULL DEFAULT 'USD', created_at REAL NOT NULL, UNIQUE(company_id, period, category))",
    )),
)

class BudgetEngine:
    """Presupuesto vs real por categoria/periodo."""

    def __init__(self, db, clock):
        self._db = db
        self._clock = clock
        MigrationRunner(db, "nexo.budgets",
                        _MIGRATIONS).run(clock)

    def set_budget(self, *, company_id, period,
                   category, budgeted,
                   currency="USD") -> dict:
        from decimal import Decimal as _D
        val = _D(str(budgeted)).quantize(_D(_Q))
        if val < 0:
            raise ValueError("presupuesto >= 0")
        bid = "BGT-" + str(uuid.uuid4())
        now = self._clock.now()
        with self._db.transaction() as cursor:
            cursor.execute(
                "INSERT INTO nexo_budgets"
                " (budget_id, company_id, period,"
                " category, budgeted, actual,"
                " currency, created_at)"
                " VALUES (?, ?, ?, ?, ?, '0', ?, ?)"
                " ON CONFLICT(company_id, period,"
                " category) DO UPDATE SET budgeted"
                " = excluded.budgeted",
                (bid, company_id, period, category,
                 str(val), currency, now))
        return self.get_budget(company_id, period,
                               category)

    def get_budget(self, company_id, period,
                   category) -> Optional[dict]:
        from decimal import Decimal as _D
        row = self._db.query_one(
            "SELECT * FROM nexo_budgets WHERE"
            " company_id = ? AND period = ? AND"
            " category = ?",
            (company_id, period, category))
        if not row:
            return None
        b = _D(str(row["budgeted"])).quantize(_D(_Q))
        a = _D(str(row["actual"])).quantize(_D(_Q))
        vari = (a - b).quantize(_D(_Q))
        pct = (round(float(vari / b) * 100, 2)
               if b > 0 else 0.0)
        return {"company_id": company_id,
                "period": str(row["period"]),
                "category": str(row["category"]),
                "budgeted": str(b),
                "actual": str(a),
                "variation": str(vari),
                "variation_pct": pct,
                "over_budget": vari > 0}

    def register_actual(self, *, company_id, period,
                        category, amount) -> dict:
        from decimal import Decimal as _D
        amt = _D(str(amount)).quantize(_D(_Q))
        with self._db.transaction() as cursor:
            cursor.execute(
                "UPDATE nexo_budgets SET actual ="
                " actual + ? WHERE company_id = ?"
                " AND period = ? AND category = ?",
                (str(amt), company_id, period,
                 category))
        return self.get_budget(company_id, period,
                               category)

    def budgets_of(self, company_id,
                   period) -> List[dict]:
        rows = self._db.query_all(
            "SELECT period, category FROM"
            " nexo_budgets WHERE company_id = ?"
            " AND period = ? ORDER BY category",
            (company_id, period))
        return [self.get_budget(company_id,
                                str(r["period"]),
                                str(r["category"]))
                for r in rows]

    def alerts(self, company_id,
               period) -> List[dict]:
        alertas = []
        for b in self.budgets_of(company_id,
                                 period):
            if b and b["over_budget"]:
                alertas.append({
                    "category": b["category"],
                    "budgeted": b["budgeted"],
                    "actual": b["actual"],
                    "variation":
                        b["variation"],
                    "variation_pct":
                        b["variation_pct"]})
        return alertas
