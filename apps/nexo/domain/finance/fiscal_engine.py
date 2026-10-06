
"""Fiscal Engine - motor fiscal configurable (NG5).
Tipos de impuesto (IVA, RENTA, RETENCION, MUNICIPAL,
ESPECIAL) con tasas por pais. Calculo con REDONDEO
COMERCIAL (ROUND_HALF_UP, estandar fiscal: 130.065 ->
130.07). Obligaciones declarar -> pagar. Montos
SIEMPRE 2 decimales (regla 61). La conexion con cada
Hacienda es conector externo; el motor fiscal es NEXO."""
from __future__ import annotations
from decimal import (Decimal as _D,
                     ROUND_HALF_UP as _UP)
from typing import List, Optional
import uuid
from shared_engines.common.clocks import Clock
from shared_engines.storage.database import Database
from shared_engines.storage.migrations import (
    Migration, MigrationRunner)

TAX_TYPES = ("IVA", "RENTA", "RETENCION",
             "MUNICIPAL", "ESPECIAL")
_Q = "0.01"

def _q2(v) -> _D:
    """Cuantizacion comercial fiscal (HALF_UP)."""
    return _D(str(v)).quantize(_D(_Q),
                               rounding=_UP)

_MIGRATIONS = (
    Migration(1, "nexo_fiscal_rates", (
        "CREATE TABLE IF NOT EXISTS nexo_fiscal_rates (rate_id TEXT PRIMARY KEY, country TEXT NOT NULL, tax_type TEXT NOT NULL, rate_pct TEXT NOT NULL, active INTEGER NOT NULL DEFAULT 1, created_at REAL NOT NULL, UNIQUE(country, tax_type))",
    )),
    Migration(2, "nexo_fiscal_obligations", (
        "CREATE TABLE IF NOT EXISTS nexo_fiscal_obligations (obligation_id TEXT PRIMARY KEY, company_id TEXT NOT NULL, period TEXT NOT NULL, tax_type TEXT NOT NULL, base TEXT NOT NULL, tax_amount TEXT NOT NULL, paid TEXT NOT NULL DEFAULT '0', currency TEXT NOT NULL DEFAULT 'USD', status TEXT NOT NULL DEFAULT 'PENDING', created_at REAL NOT NULL)",
    )),
)

class FiscalEngine:
    """Motor fiscal configurable (Decimal 2d)."""

    def __init__(self, db, clock):
        self._db = db
        self._clock = clock
        MigrationRunner(db, "nexo.fiscal",
                        _MIGRATIONS).run(clock)

    def set_rate(self, *, country, tax_type,
                 rate_pct) -> dict:
        if tax_type not in TAX_TYPES:
            raise ValueError(
                "tipo invalido: " + str(tax_type))
        rate = _q2(rate_pct)
        if rate < 0:
            raise ValueError("tasa >= 0")
        rid = "FR-" + str(uuid.uuid4())
        now = self._clock.now()
        with self._db.transaction() as cursor:
            cursor.execute(
                "INSERT INTO nexo_fiscal_rates"
                " (rate_id, country, tax_type,"
                " rate_pct, active, created_at)"
                " VALUES (?, ?, ?, ?, 1, ?)"
                " ON CONFLICT(country, tax_type)"
                " DO UPDATE SET rate_pct ="
                " excluded.rate_pct",
                (rid, country, tax_type, str(rate),
                 now))
        return {"country": country,
                "tax_type": tax_type,
                "rate_pct": str(rate)}

    def get_rate(self, country,
                 tax_type) -> str:
        row = self._db.query_one(
            "SELECT rate_pct FROM nexo_fiscal_rates"
            " WHERE country = ? AND tax_type = ?"
            " AND active = 1", (country, tax_type))
        if not row:
            raise ValueError("sin tasa: " + country
                             + "/" + tax_type)
        return str(_q2(row["rate_pct"]))

    def calculate_tax(self, *, base, tax_type,
                      country="SV") -> str:
        b = _q2(base)
        if b < 0:
            raise ValueError("base >= 0")
        rate = _D(self.get_rate(country, tax_type))
        return str(_q2(b * rate / _D("100")))

    def declare_obligation(self, *, company_id,
                           period, tax_type, base,
                           country="SV",
                           currency="USD") -> dict:
        tax = self.calculate_tax(
            base=base, tax_type=tax_type,
            country=country)
        oid = "FOB-" + str(uuid.uuid4())
        now = self._clock.now()
        with self._db.transaction() as cursor:
            cursor.execute(
                "INSERT INTO"
                " nexo_fiscal_obligations"
                " (obligation_id, company_id,"
                " period, tax_type, base,"
                " tax_amount, paid, currency,"
                " status, created_at)"
                " VALUES (?, ?, ?, ?, ?, ?, '0', ?,"
                " 'PENDING', ?)",
                (oid, company_id, period, tax_type,
                 str(_q2(base)), tax, currency,
                 now))
        return self.get_obligation(oid)

    def get_obligation(self,
                       obligation_id) -> Optional[dict]:
        row = self._db.query_one(
            "SELECT * FROM nexo_fiscal_obligations"
            " WHERE obligation_id = ?",
            (obligation_id,))
        if not row:
            return None
        tax = _q2(row["tax_amount"])
        paid = _q2(row["paid"])
        return {"obligation_id":
                    str(row["obligation_id"]),
                "company_id":
                    str(row["company_id"]),
                "period": str(row["period"]),
                "tax_type": str(row["tax_type"]),
                "base": str(row["base"]),
                "tax_amount": str(tax),
                "paid": str(paid),
                "balance": str(tax - paid),
                "currency": str(row["currency"]),
                "status": str(row["status"])}

    def register_payment(self, *, obligation_id,
                         amount) -> dict:
        obl = self.get_obligation(obligation_id)
        if not obl:
            raise KeyError(obligation_id)
        pay = _q2(amount)
        if pay <= 0:
            raise ValueError("pago positivo")
        bal = _D(obl["balance"])
        if pay > bal:
            raise ValueError("pago mayor que saldo")
        new_paid = _q2(_D(obl["paid"]) + pay)
        tax = _D(obl["tax_amount"])
        status = ("PAID" if new_paid == tax
                  else "PARTIAL")
        self._db.execute(
            "UPDATE nexo_fiscal_obligations SET"
            " paid = ?, status = ? WHERE"
            " obligation_id = ?",
            (str(new_paid), status,
             obligation_id))
        return self.get_obligation(obligation_id)

    def obligations_of(self, company_id,
                       period="") -> List[dict]:
        if period:
            rows = self._db.query_all(
                "SELECT obligation_id FROM"
                " nexo_fiscal_obligations WHERE"
                " company_id = ? AND period = ?"
                " ORDER BY created_at",
                (company_id, period))
        else:
            rows = self._db.query_all(
                "SELECT obligation_id FROM"
                " nexo_fiscal_obligations WHERE"
                " company_id = ?"
                " ORDER BY created_at",
                (company_id,))
        return [self.get_obligation(
            str(r["obligation_id"]))
            for r in rows]

    def summary(self, company_id, period) -> dict:
        obls = self.obligations_of(company_id,
                                   period)
        declared = _D("0")
        paid = _D("0")
        for o in obls:
            declared = (declared
                        + _D(o["tax_amount"]))
            paid = paid + _D(o["paid"])
        declared = _q2(declared)
        paid = _q2(paid)
        return {"company_id": company_id,
                "period": period,
                "declared": str(declared),
                "paid": str(paid),
                "pending": str(_q2(declared
                                   - paid)),
                "obligations": len(obls)}
