
"""Operational Metrics Engine - NEXO / ZYRA (migrado
mejorado). Metricas operativas por empresa y periodo,
calculadas de nexo_operations y PERSISTIDAS (el viejo
era en memoria). Montos Decimal (regla 61). Sirve para
reportes a gobiernos, alcaldias y bancos."""
from __future__ import annotations
from typing import List
import uuid
from shared_engines.common.clocks import Clock
from shared_engines.storage.database import Database
from shared_engines.storage.migrations import (
    Migration, MigrationRunner)

_MIGRATIONS = (
    Migration(1, "nexo_operation_metrics", (
        "CREATE TABLE IF NOT EXISTS nexo_operation_metrics (metric_id TEXT PRIMARY KEY, company_id TEXT NOT NULL, period TEXT NOT NULL, metric_name TEXT NOT NULL, metric_value TEXT NOT NULL, computed_at REAL NOT NULL)",
    )),
)

class OperationalMetricsEngine:
    """Metricas operativas (persistente)."""

    def __init__(self, db, clock):
        self._db = db
        self._clock = clock
        MigrationRunner(db, "nexo.opmetrics",
                        _MIGRATIONS).run(clock)

    def compute_company_metrics(self, *, company_id,
                                period) -> dict:
        from decimal import Decimal as _D
        ops = self._db.query_all(
            "SELECT status, amount FROM"
            " nexo_operations"
            " WHERE company_id = ?", (company_id,))
        total = len(ops)
        completed = sum(1 for o in ops
                        if str(o["status"])
                        == "COMPLETED")
        active_amt = _D("0")
        for o in ops:
            if str(o["status"]) in ("COMPLETED",
                                    "IN_PROGRESS"):
                active_amt = (active_amt
                              + _D(str(o["amount"])))
        success = (round(completed * 100.0 / total, 2)
                   if total else 0.0)
        metrics = {"total_operations": str(total),
                   "completed_operations":
                       str(completed),
                   "active_amount": str(active_amt),
                   "success_rate_pct": str(success)}
        now = self._clock.now()
        with self._db.transaction() as cursor:
            for name, value in metrics.items():
                cursor.execute(
                    "INSERT INTO"
                    " nexo_operation_metrics"
                    " (metric_id, company_id, period,"
                    " metric_name, metric_value,"
                    " computed_at)"
                    " VALUES (?, ?, ?, ?, ?, ?)",
                    ("MET-" + str(uuid.uuid4()),
                     company_id, period, name,
                     value, now))
        return {"company_id": company_id,
                "period": period,
                "metrics": metrics}

    def get_metrics(self, company_id,
                    period="") -> List[dict]:
        if period:
            rows = self._db.query_all(
                "SELECT * FROM nexo_operation_metrics"
                " WHERE company_id = ? AND period = ?"
                " ORDER BY computed_at",
                (company_id, period))
        else:
            rows = self._db.query_all(
                "SELECT * FROM nexo_operation_metrics"
                " WHERE company_id = ?"
                " ORDER BY computed_at",
                (company_id,))
        return [{"period": str(r["period"]),
                 "metric_name": str(r["metric_name"]),
                 "metric_value": str(r["metric_value"]),
                 "computed_at": float(r["computed_at"])}
                for r in rows]
