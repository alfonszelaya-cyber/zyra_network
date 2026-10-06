
"""Fiscal Calendar Engine - calendario de vencimientos
fiscales (NG5). Fechas limite por impuesto y periodo,
proximos vencimientos, vencidos, marcado de
presentacion. Persistente."""
from __future__ import annotations
from typing import List, Optional
import uuid
from shared_engines.common.clocks import Clock
from shared_engines.storage.database import Database
from shared_engines.storage.migrations import (
    Migration, MigrationRunner)

_MIGRATIONS = (
    Migration(1, "nexo_fiscal_deadlines", (
        "CREATE TABLE IF NOT EXISTS nexo_fiscal_deadlines (deadline_id TEXT PRIMARY KEY, company_id TEXT NOT NULL, period TEXT NOT NULL, tax_type TEXT NOT NULL, due_at REAL NOT NULL, description TEXT NOT NULL DEFAULT '', filed INTEGER NOT NULL DEFAULT 0, created_at REAL NOT NULL)",
    )),
)

class FiscalCalendarEngine:
    """Vencimientos fiscales (persistente)."""

    def __init__(self, db, clock):
        self._db = db
        self._clock = clock
        MigrationRunner(db, "nexo.fiscalcal",
                        _MIGRATIONS).run(clock)

    def add_deadline(self, *, company_id, period,
                     tax_type, due_days,
                     description="") -> dict:
        did = "FDL-" + str(uuid.uuid4())
        now = self._clock.now()
        due = now + (int(due_days) * 86400)
        with self._db.transaction() as cursor:
            cursor.execute(
                "INSERT INTO"
                " nexo_fiscal_deadlines"
                " (deadline_id, company_id, period,"
                " tax_type, due_at, description,"
                " filed, created_at)"
                " VALUES (?, ?, ?, ?, ?, ?, 0, ?)",
                (did, company_id, period, tax_type,
                 due, description, now))
        return {"deadline_id": did,
                "company_id": company_id,
                "period": period,
                "tax_type": tax_type,
                "due_at": due,
                "filed": False}

    def _row(self, r) -> dict:
        return {"deadline_id":
                    str(r["deadline_id"]),
                "company_id":
                    str(r["company_id"]),
                "period": str(r["period"]),
                "tax_type": str(r["tax_type"]),
                "due_at": float(r["due_at"]),
                "description":
                    str(r["description"]),
                "filed": bool(r["filed"])}

    def upcoming(self, company_id,
                 days=30) -> List[dict]:
        now = self._clock.now()
        limit = now + (int(days) * 86400)
        rows = self._db.query_all(
            "SELECT * FROM nexo_fiscal_deadlines"
            " WHERE company_id = ? AND filed = 0"
            " AND due_at >= ? AND due_at <= ?"
            " ORDER BY due_at",
            (company_id, now, limit))
        return [self._row(r) for r in rows]

    def overdue(self, company_id) -> List[dict]:
        now = self._clock.now()
        rows = self._db.query_all(
            "SELECT * FROM nexo_fiscal_deadlines"
            " WHERE company_id = ? AND filed = 0"
            " AND due_at < ? ORDER BY due_at",
            (company_id, now))
        return [self._row(r) for r in rows]

    def mark_filed(self, deadline_id) -> dict:
        self._db.execute(
            "UPDATE nexo_fiscal_deadlines SET"
            " filed = 1 WHERE deadline_id = ?",
            (deadline_id,))
        row = self._db.query_one(
            "SELECT * FROM nexo_fiscal_deadlines"
            " WHERE deadline_id = ?", (deadline_id,))
        return self._row(row) if row else None
