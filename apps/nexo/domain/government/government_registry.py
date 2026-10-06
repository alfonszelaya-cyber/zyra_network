
"""Government Registry - instituciones y presupuesto
publico (NG6). Programas con ejecucion presupuestaria
en 4 fases: presupuesto -> comprometido -> devengado
-> pagado, con validacion de saldos en cada fase.
Contabilidad gubernamental real para alcaldias,
ministerios e instituciones. Decimal 2d (regla 61)."""
from __future__ import annotations
from typing import List, Optional
import uuid
from shared_engines.common.clocks import Clock
from shared_engines.storage.database import Database
from shared_engines.storage.migrations import (
    Migration, MigrationRunner)

_Q = "0.01"
INSTITUTION_KINDS = ("MINISTRY", "MUNICIPALITY",
                     "AGENCY", "AUTONOMOUS")

_MIGRATIONS = (
    Migration(1, "nexo_gov_institutions", (
        "CREATE TABLE IF NOT EXISTS nexo_gov_institutions (institution_id TEXT PRIMARY KEY, name TEXT NOT NULL, kind TEXT NOT NULL DEFAULT 'AGENCY', country TEXT NOT NULL DEFAULT 'SV', active INTEGER NOT NULL DEFAULT 1, created_at REAL NOT NULL)",
    )),
    Migration(2, "nexo_gov_programs", (
        "CREATE TABLE IF NOT EXISTS nexo_gov_programs (program_id TEXT PRIMARY KEY, institution_id TEXT NOT NULL, name TEXT NOT NULL, period TEXT NOT NULL, budgeted TEXT NOT NULL DEFAULT '0', committed TEXT NOT NULL DEFAULT '0', accrued TEXT NOT NULL DEFAULT '0', paid TEXT NOT NULL DEFAULT '0', currency TEXT NOT NULL DEFAULT 'USD', status TEXT NOT NULL DEFAULT 'ACTIVE', created_at REAL NOT NULL)",
    )),
)

class GovernmentRegistry:
    """Instituciones + presupuesto publico ejecutado."""

    def __init__(self, db, clock):
        self._db = db
        self._clock = clock
        MigrationRunner(db, "nexo.govreg",
                        _MIGRATIONS).run(clock)

    def create_institution(self, *, name,
                           kind="AGENCY",
                           country="SV") -> dict:
        if kind not in INSTITUTION_KINDS:
            kind = "AGENCY"
        iid = "GOV-" + str(uuid.uuid4())
        now = self._clock.now()
        with self._db.transaction() as cursor:
            cursor.execute(
                "INSERT INTO"
                " nexo_gov_institutions"
                " (institution_id, name, kind,"
                " country, active, created_at)"
                " VALUES (?, ?, ?, ?, 1, ?)",
                (iid, name, kind, country, now))
        return {"institution_id": iid,
                "name": name, "kind": kind,
                "country": country,
                "active": True}

    def institutions(self,
                     active=True) -> List[dict]:
        rows = self._db.query_all(
            "SELECT * FROM nexo_gov_institutions"
            " WHERE active = ? ORDER BY name",
            (1 if active else 0,))
        return [{"institution_id":
                     str(r["institution_id"]),
                 "name": str(r["name"]),
                 "kind": str(r["kind"]),
                 "country": str(r["country"]),
                 "active": bool(r["active"])}
                for r in rows]

    def create_program(self, *, institution_id,
                       name, period, budgeted,
                       currency="USD") -> dict:
        from decimal import Decimal as _D
        b = _D(str(budgeted)).quantize(_D(_Q))
        if b < 0:
            raise ValueError("presupuesto >= 0")
        pid = "PRG-" + str(uuid.uuid4())
        now = self._clock.now()
        with self._db.transaction() as cursor:
            cursor.execute(
                "INSERT INTO nexo_gov_programs"
                " (program_id, institution_id,"
                " name, period, budgeted,"
                " committed, accrued, paid,"
                " currency, status, created_at)"
                " VALUES (?, ?, ?, ?, ?, '0', '0',"
                " '0', ?, 'ACTIVE', ?)",
                (pid, institution_id, name,
                 period, str(b), currency, now))
        return self.get_program(pid)

    def get_program(self,
                    program_id) -> Optional[dict]:
        from decimal import Decimal as _D
        row = self._db.query_one(
            "SELECT * FROM nexo_gov_programs WHERE"
            " program_id = ?", (program_id,))
        if not row:
            return None
        q = lambda c: str(_D(
            str(row[c])).quantize(_D(_Q)))
        b = _D(q("budgeted"))
        paid = _D(q("paid"))
        pct = (round(float(paid / b) * 100, 2)
               if b > 0 else 0.0)
        return {"program_id":
                    str(row["program_id"]),
                "institution_id":
                    str(row["institution_id"]),
                "name": str(row["name"]),
                "period": str(row["period"]),
                "budgeted": q("budgeted"),
                "committed": q("committed"),
                "accrued": q("accrued"),
                "paid": q("paid"),
                "available_budget": str(
                    (b - _D(q("committed"))
                     ).quantize(_D(_Q))),
                "execution_pct": pct,
                "currency":
                    str(row["currency"]),
                "status": str(row["status"])}

    def commit_funds(self, *, program_id,
                     amount) -> dict:
        from decimal import Decimal as _D
        p = self.get_program(program_id)
        amt = _D(str(amount)).quantize(_D(_Q))
        if amt <= 0:
            raise ValueError("monto positivo")
        avail = (_D(p["budgeted"])
                 - _D(p["committed"]))
        if amt > avail:
            raise ValueError(
                "compromiso excede presupuesto:"
                " disponible " + str(avail))
        new = (_D(p["committed"])
               + amt).quantize(_D(_Q))
        self._db.execute(
            "UPDATE nexo_gov_programs SET"
            " committed = ? WHERE program_id = ?",
            (str(new), program_id))
        return self.get_program(program_id)

    def accrue(self, *, program_id, amount) -> dict:
        from decimal import Decimal as _D
        p = self.get_program(program_id)
        amt = _D(str(amount)).quantize(_D(_Q))
        if amt <= 0:
            raise ValueError("monto positivo")
        avail = (_D(p["committed"])
                 - _D(p["accrued"]))
        if amt > avail:
            raise ValueError(
                "devengo excede comprometido:"
                " disponible " + str(avail))
        new = (_D(p["accrued"])
               + amt).quantize(_D(_Q))
        self._db.execute(
            "UPDATE nexo_gov_programs SET"
            " accrued = ? WHERE program_id = ?",
            (str(new), program_id))
        return self.get_program(program_id)

    def pay(self, *, program_id, amount) -> dict:
        from decimal import Decimal as _D
        p = self.get_program(program_id)
        amt = _D(str(amount)).quantize(_D(_Q))
        if amt <= 0:
            raise ValueError("monto positivo")
        avail = (_D(p["accrued"])
                 - _D(p["paid"]))
        if amt > avail:
            raise ValueError(
                "pago excede devengado:"
                " disponible " + str(avail))
        new = (_D(p["paid"])
               + amt).quantize(_D(_Q))
        self._db.execute(
            "UPDATE nexo_gov_programs SET"
            " paid = ? WHERE program_id = ?",
            (str(new), program_id))
        return self.get_program(program_id)

    def programs_of(self, institution_id,
                    period="") -> List[dict]:
        if period:
            rows = self._db.query_all(
                "SELECT program_id FROM"
                " nexo_gov_programs WHERE"
                " institution_id = ? AND period = ?"
                " ORDER BY created_at",
                (institution_id, period))
        else:
            rows = self._db.query_all(
                "SELECT program_id FROM"
                " nexo_gov_programs WHERE"
                " institution_id = ?"
                " ORDER BY created_at",
                (institution_id,))
        return [self.get_program(
            str(r["program_id"]))
            for r in rows]

    def all_programs(self) -> List[dict]:
        rows = self._db.query_all(
            "SELECT program_id FROM"
            " nexo_gov_programs ORDER BY"
            " created_at")
        return [self.get_program(
            str(r["program_id"]))
            for r in rows]
