
"""Fiscal Reconciliation Engine - conciliacion
fiscal-contable (NG5). Compara obligaciones fiscales
declaradas vs lo registrado en contabilidad por tipo
de impuesto. Diferencias reportadas y persistidas."""
from __future__ import annotations
from typing import Dict, List
import json as _j
import uuid
from shared_engines.common.clocks import Clock
from shared_engines.storage.database import Database
from shared_engines.storage.migrations import (
    Migration, MigrationRunner)

_Q = "0.01"

_MIGRATIONS = (
    Migration(1, "nexo_fiscal_reconciliations", (
        "CREATE TABLE IF NOT EXISTS nexo_fiscal_reconciliations (reconciliation_id TEXT PRIMARY KEY, company_id TEXT NOT NULL, period TEXT NOT NULL, matched INTEGER NOT NULL, differences_json TEXT NOT NULL DEFAULT '[]', created_at REAL NOT NULL)",
    )),
)

class FiscalReconciliationEngine:
    """Conciliacion fiscal vs contable."""

    def __init__(self, db, clock):
        self._db = db
        self._clock = clock
        MigrationRunner(db, "nexo.fiscalrec",
                        _MIGRATIONS).run(clock)

    def reconcile(self, *, company_id, period,
                  fiscal_by_type,
                  book_by_type) -> dict:
        from decimal import Decimal as _D
        tipos = set(list(fiscal_by_type.keys())
                    + list(book_by_type.keys()))
        items = []
        matched = 0
        for t in sorted(tipos):
            f = _D(str(fiscal_by_type.get(t, "0"))
                   ).quantize(_D(_Q))
            b = _D(str(book_by_type.get(t, "0"))
                   ).quantize(_D(_Q))
            ok = f == b
            if ok:
                matched = matched + 1
            items.append({
                "tax_type": t,
                "fiscal": str(f),
                "book": str(b),
                "difference":
                    str((f - b).quantize(_D(_Q))),
                "matched": ok})
        rid = "FREC-" + str(uuid.uuid4())
        now = self._clock.now()
        with self._db.transaction() as cursor:
            cursor.execute(
                "INSERT INTO"
                " nexo_fiscal_reconciliations"
                " (reconciliation_id, company_id,"
                " period, matched,"
                " differences_json, created_at)"
                " VALUES (?, ?, ?, ?, ?, ?)",
                (rid, company_id, period, matched,
                 _j.dumps(items, default=str),
                 now))
        return {"reconciliation_id": rid,
                "company_id": company_id,
                "period": period,
                "matched": matched,
                "total": len(items),
                "all_matched":
                    matched == len(items),
                "items": items}
