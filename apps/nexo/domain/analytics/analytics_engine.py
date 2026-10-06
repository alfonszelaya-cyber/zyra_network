
"""Nexo Analytics Engine - analitica del periodo (NG7).
Montos SIEMPRE 2 decimales (regla 61)."""
from __future__ import annotations
from typing import Dict, List
import uuid
from shared_engines.common.clocks import Clock
from shared_engines.storage.database import Database
from shared_engines.storage.migrations import (
    Migration, MigrationRunner)

_Q = "0.01"

_MIGRATIONS = (
    Migration(1, "nexo_analytics", (
        "CREATE TABLE IF NOT EXISTS nexo_analytics (analysis_id TEXT PRIMARY KEY, company_id TEXT NOT NULL, period TEXT NOT NULL, metric_name TEXT NOT NULL, metric_value TEXT NOT NULL, computed_at REAL NOT NULL)",
    )),
)

class NexoAnalyticsEngine:
    """Analitica de periodo persistida."""

    def __init__(self, db, clock):
        self._db = db
        self._clock = clock
        MigrationRunner(db, "nexo.analytics",
                        _MIGRATIONS).run(clock)

    def compute_from(self, *, company_id, period,
                     records) -> Dict:
        from decimal import Decimal as _D
        income = _D("0").quantize(_D(_Q))
        expense = _D("0").quantize(_D(_Q))
        count = 0
        for r in records or []:
            rtype = str(r.get("type", ""))
            amt = _D(str(r.get("amount", "0"))
                     ).quantize(_D(_Q))
            count = count + 1
            if rtype == "INCOME":
                income = income + amt
            elif rtype == "EXPENSE":
                expense = expense + amt
        net = income - expense
        metrics = {
            "total_income": str(income),
            "total_expense": str(expense),
            "net": str(net),
            "record_count": str(count)}
        now = self._clock.now()
        with self._db.transaction() as cursor:
            for name, value in metrics.items():
                cursor.execute(
                    "INSERT INTO nexo_analytics"
                    " (analysis_id, company_id,"
                    " period, metric_name,"
                    " metric_value, computed_at)"
                    " VALUES (?, ?, ?, ?, ?, ?)",
                    ("AN-" + str(uuid.uuid4()),
                     company_id, period, name,
                     value, now))
        return {"company_id": company_id,
                "period": period,
                "metrics": metrics}

    def history(self, company_id,
                period="") -> List[dict]:
        if period:
            rows = self._db.query_all(
                "SELECT * FROM nexo_analytics"
                " WHERE company_id = ? AND"
                " period = ? ORDER BY computed_at",
                (company_id, period))
        else:
            rows = self._db.query_all(
                "SELECT * FROM nexo_analytics"
                " WHERE company_id = ?"
                " ORDER BY computed_at",
                (company_id,))
        return [{"period": str(r["period"]),
                 "metric_name":
                     str(r["metric_name"]),
                 "metric_value":
                     str(r["metric_value"])}
                for r in rows]
