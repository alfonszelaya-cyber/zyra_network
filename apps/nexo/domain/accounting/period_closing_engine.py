
"""Period Closing Engine - cierres contables (NG3).
Bloqueo real, reapertura auditada, asiento de cierre
SIN lineas vacias."""
from __future__ import annotations
from typing import List, Optional
import uuid
from shared_engines.common.clocks import Clock
from shared_engines.storage.database import Database
from shared_engines.storage.migrations import (
    Migration, MigrationRunner)

_MIGRATIONS = (
    Migration(1, "nexo_periods", (
        "CREATE TABLE IF NOT EXISTS nexo_periods (company_id TEXT NOT NULL, period TEXT NOT NULL, status TEXT NOT NULL DEFAULT 'OPEN', closed_by TEXT, closed_at REAL, reopened_by TEXT, reopened_at REAL, PRIMARY KEY(company_id, period))",
    )),
    Migration(2, "nexo_period_close_events", (
        "CREATE TABLE IF NOT EXISTS nexo_period_close_events (event_id TEXT PRIMARY KEY, company_id TEXT NOT NULL, period TEXT NOT NULL, event_type TEXT NOT NULL, actor TEXT NOT NULL DEFAULT '', detail TEXT NOT NULL DEFAULT '', created_at REAL NOT NULL)",
    )),
)

class PeriodClosingEngine:
    """Cierre y reapertura auditada de periodos."""

    def __init__(self, db, clock):
        self._db = db
        self._clock = clock
        MigrationRunner(db, "nexo.periods",
                        _MIGRATIONS).run(clock)

    def _log(self, cursor, company_id, period,
             event_type, actor, detail=""):
        cursor.execute(
            "INSERT INTO nexo_period_close_events"
            " (event_id, company_id, period,"
            " event_type, actor, detail, created_at)"
            " VALUES (?, ?, ?, ?, ?, ?, ?)",
            ("PCE-" + str(uuid.uuid4()), company_id,
             period, event_type, actor, detail,
             self._clock.now()))

    def ensure_open(self, company_id, period) -> dict:
        row = self._db.query_one(
            "SELECT * FROM nexo_periods WHERE"
            " company_id = ? AND period = ?",
            (company_id, period))
        if row is None:
            with self._db.transaction() as cursor:
                cursor.execute(
                    "INSERT INTO nexo_periods"
                    " (company_id, period, status)"
                    " VALUES (?, ?, 'OPEN')",
                    (company_id, period))
                self._log(cursor, company_id, period,
                          "CREATED", "system",
                          "periodo creado abierto")
        return self.get_period(company_id, period)

    def get_period(self, company_id,
                   period) -> Optional[dict]:
        row = self._db.query_one(
            "SELECT * FROM nexo_periods WHERE"
            " company_id = ? AND period = ?",
            (company_id, period))
        if not row:
            return None
        return {"company_id": str(row["company_id"]),
                "period": str(row["period"]),
                "status": str(row["status"]),
                "closed_by": (str(row["closed_by"])
                              if row["closed_by"]
                              else None),
                "reopened_by":
                    (str(row["reopened_by"])
                     if row["reopened_by"]
                     else None)}

    def assert_open(self, company_id, period) -> None:
        p = self.get_period(company_id, period)
        if p is not None and p["status"] != "OPEN":
            raise ValueError(
                "periodo cerrado: " + period)

    def close_period(self, *, company_id, period,
                     actor) -> dict:
        p = self.get_period(company_id, period)
        if p is None:
            self.ensure_open(company_id, period)
            p = self.get_period(company_id, period)
        if p["status"] == "CLOSED":
            raise ValueError(
                "ya cerrado: " + period)
        now = self._clock.now()
        with self._db.transaction() as cursor:
            cursor.execute(
                "UPDATE nexo_periods SET"
                " status = 'CLOSED', closed_by = ?,"
                " closed_at = ? WHERE company_id = ?"
                " AND period = ?",
                (actor, now, company_id, period))
            self._log(cursor, company_id, period,
                      "CLOSED", actor)
        return self.get_period(company_id, period)

    def reopen_period(self, *, company_id, period,
                      actor, reason="") -> dict:
        p = self.get_period(company_id, period)
        if p is None:
            raise ValueError("no existe: " + period)
        if p["status"] != "CLOSED":
            raise ValueError("no esta cerrado")
        now = self._clock.now()
        with self._db.transaction() as cursor:
            cursor.execute(
                "UPDATE nexo_periods SET"
                " status = 'OPEN', reopened_by = ?,"
                " reopened_at = ? WHERE"
                " company_id = ? AND period = ?",
                (actor, now, company_id, period))
            self._log(cursor, company_id, period,
                      "REOPENED", actor, reason)
        return self.get_period(company_id, period)

    def events_of(self, company_id,
                  period) -> List[dict]:
        rows = self._db.query_all(
            "SELECT * FROM nexo_period_close_events"
            " WHERE company_id = ? AND period = ?"
            " ORDER BY created_at",
            (company_id, period))
        return [{"event_type": str(r["event_type"]),
                 "actor": str(r["actor"]),
                 "detail": str(r["detail"]),
                 "created_at":
                     float(r["created_at"])}
                for r in rows]

    def closing_entry(self, *, company_id, period,
                      ingresos, gastos) -> dict:
        """Asiento de cierre: solo lineas con
        movimiento (nunca 0/0)."""
        from decimal import Decimal as _D
        ing = _D(str(ingresos)).quantize(_D("0.01"))
        gas = _D(str(gastos)).quantize(_D("0.01"))
        utilidad = ing - gas
        lines = []
        if ing != 0:
            lines.append(
                {"account_code": "4000",
                 "debit": str(ing),
                 "credit": "0"})
        if gas != 0:
            lines.append(
                {"account_code": "5000",
                 "debit": "0",
                 "credit": str(gas)})
        if utilidad > 0:
            lines.append(
                {"account_code": "3100",
                 "debit": "0",
                 "credit": str(utilidad)})
        elif utilidad < 0:
            lines.append(
                {"account_code": "3100",
                 "debit": str(-utilidad),
                 "credit": "0"})
        return {"period": period,
                "utilidad": str(utilidad),
                "lines": lines}
