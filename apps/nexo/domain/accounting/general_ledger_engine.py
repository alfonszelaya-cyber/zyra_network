
"""General Ledger Engine - libro mayor (NG3).
Movimientos con debit/credit SIEMPRE cuantizados a 2
decimales (regla 61). Acepta period_engine opcional:
rechaza movimientos en periodo cerrado. Persistente."""
from __future__ import annotations
from typing import List, Optional
import uuid
from shared_engines.common.clocks import Clock
from shared_engines.storage.database import Database
from shared_engines.storage.migrations import (
    Migration, MigrationRunner)

_Q = "0.01"

_MIGRATIONS = (
    Migration(1, "nexo_gl_entries", (
        "CREATE TABLE IF NOT EXISTS nexo_gl_entries (entry_id TEXT PRIMARY KEY, company_id TEXT NOT NULL, period TEXT NOT NULL, account_code TEXT NOT NULL, debit TEXT NOT NULL DEFAULT '0', credit TEXT NOT NULL DEFAULT '0', cost_center TEXT NOT NULL DEFAULT '', source_ref TEXT NOT NULL DEFAULT '', created_at REAL NOT NULL)",
    )),
)

class GeneralLedgerEngine:
    """Libro mayor persistente (Decimal 2 decimales)."""

    def __init__(self, db, clock,
                 period_engine=None):
        self._db = db
        self._clock = clock
        self._periods = period_engine
        MigrationRunner(db, "nexo.gl",
                        _MIGRATIONS).run(clock)

    def _check_open(self, company_id, period):
        if self._periods is not None:
            gate = getattr(self._periods,
                           "assert_open", None)
            if callable(gate):
                gate(company_id, period)

    def post_entry(self, *, company_id, period,
                   account_code, debit="0",
                   credit="0", cost_center="",
                   source_ref="") -> dict:
        from decimal import Decimal as _D
        self._check_open(company_id, period)
        d = _D(str(debit)).quantize(_D(_Q))
        c = _D(str(credit)).quantize(_D(_Q))
        if d < 0 or c < 0:
            raise ValueError(
                "debit/credit no negativos")
        if d == 0 and c == 0:
            raise ValueError(
                "movimiento vacio")
        eid = "GL-" + str(uuid.uuid4())
        now = self._clock.now()
        with self._db.transaction() as cursor:
            cursor.execute(
                "INSERT INTO nexo_gl_entries"
                " (entry_id, company_id, period,"
                " account_code, debit, credit,"
                " cost_center, source_ref,"
                " created_at)"
                " VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)",
                (eid, company_id, period,
                 account_code, str(d), str(c),
                 cost_center, source_ref, now))
        return {"entry_id": eid,
                "company_id": company_id,
                "period": period,
                "account_code": account_code,
                "debit": str(d), "credit": str(c),
                "cost_center": cost_center,
                "source_ref": source_ref}

    def post_balanced(self, *, company_id, period,
                      lines, source_ref="") -> dict:
        from decimal import Decimal as _D
        self._check_open(company_id, period)
        activas = []
        for l in lines:
            d = _D(str(l.get("debit", "0")))
            c = _D(str(l.get("credit", "0")))
            if d != 0 or c != 0:
                activas.append(l)
        td = sum((_D(str(l.get("debit", "0")))
                  for l in activas), _D("0"))
        tc = sum((_D(str(l.get("credit", "0")))
                  for l in activas), _D("0"))
        if td != tc:
            raise ValueError(
                "asiento descuadrado: D="
                + str(td) + " C=" + str(tc))
        out = []
        for l in activas:
            out.append(self.post_entry(
                company_id=company_id,
                period=period,
                account_code=l["account_code"],
                debit=l.get("debit", "0"),
                credit=l.get("credit", "0"),
                cost_center=l.get("cost_center",
                                  ""),
                source_ref=source_ref))
        return {"posted": len(out),
                "total_debit": str(td.quantize(
                    _D(_Q))),
                "total_credit": str(tc.quantize(
                    _D(_Q))),
                "entries": out}

    def account_balance(self, company_id,
                        account_code,
                        period="") -> dict:
        from decimal import Decimal as _D
        if period:
            row = self._db.query_one(
                "SELECT"
                " COALESCE(SUM(debit),'0') AS d,"
                " COALESCE(SUM(credit),'0') AS c"
                " FROM nexo_gl_entries WHERE"
                " company_id = ? AND account_code = ?"
                " AND period = ?",
                (company_id, account_code, period))
        else:
            row = self._db.query_one(
                "SELECT"
                " COALESCE(SUM(debit),'0') AS d,"
                " COALESCE(SUM(credit),'0') AS c"
                " FROM nexo_gl_entries WHERE"
                " company_id = ? AND account_code = ?",
                (company_id, account_code))
        d = _D(str(row["d"])) if row else _D("0")
        c = _D(str(row["c"])) if row else _D("0")
        bal = (d - c).quantize(_D(_Q))
        return {"account_code": account_code,
                "debit": str(d.quantize(_D(_Q))),
                "credit": str(c.quantize(_D(_Q))),
                "balance": str(bal)}

    def trial_balance(self, company_id,
                      period="") -> List[dict]:
        from decimal import Decimal as _D
        if period:
            rows = self._db.query_all(
                "SELECT account_code,"
                " COALESCE(SUM(debit),'0') AS d,"
                " COALESCE(SUM(credit),'0') AS c"
                " FROM nexo_gl_entries WHERE"
                " company_id = ? AND period = ?"
                " GROUP BY account_code"
                " ORDER BY account_code",
                (company_id, period))
        else:
            rows = self._db.query_all(
                "SELECT account_code,"
                " COALESCE(SUM(debit),'0') AS d,"
                " COALESCE(SUM(credit),'0') AS c"
                " FROM nexo_gl_entries WHERE"
                " company_id = ?"
                " GROUP BY account_code"
                " ORDER BY account_code",
                (company_id,))
        return [{"account_code": str(r["account_code"]),
                 "debit": str(_D(str(r["d"]))
                           .quantize(_D(_Q))),
                 "credit": str(_D(str(r["c"]))
                               .quantize(_D(_Q)))}
                for r in rows]

    def entries_of(self, company_id,
                   account_code) -> List[dict]:
        rows = self._db.query_all(
            "SELECT * FROM nexo_gl_entries WHERE"
            " company_id = ? AND account_code = ?"
            " ORDER BY created_at",
            (company_id, account_code))
        return [{"entry_id": str(r["entry_id"]),
                 "period": str(r["period"]),
                 "debit": str(r["debit"]),
                 "credit": str(r["credit"]),
                 "source_ref": str(r["source_ref"])}
                for r in rows]
