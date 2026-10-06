
"""Education Economy Engine - subsidios y bonos
con trazabilidad (SM3). Decimal 2d."""
from __future__ import annotations
from decimal import (Decimal as _D,
                     ROUND_HALF_UP as _UP)
from typing import List
import uuid
from shared_engines.common.clocks import Clock
from shared_engines.storage.database import (
    Database)
from shared_engines.storage.migrations import (
    Migration, MigrationRunner)

_Q = "0.01"

_MIGRATIONS = (
    Migration(1, "sm_subsidies", (
        "CREATE TABLE IF NOT EXISTS sm_subsidies (subsidy_id TEXT PRIMARY KEY, student_id TEXT NOT NULL, subsidy_type TEXT NOT NULL, amount TEXT NOT NULL, reason TEXT NOT NULL DEFAULT '', approved_by TEXT NOT NULL DEFAULT '', created_at REAL NOT NULL)",
    )),
    Migration(2, "sm_bonuses", (
        "CREATE TABLE IF NOT EXISTS sm_bonuses (bonus_id TEXT PRIMARY KEY, student_id TEXT NOT NULL, bonus_type TEXT NOT NULL, amount TEXT NOT NULL, reason TEXT NOT NULL DEFAULT '', approved_by TEXT NOT NULL DEFAULT '', created_at REAL NOT NULL)",
    )),
)

class EducationEconomyEngine:
    """Subsidios y bonos escolares (Decimal 2d)."""

    def __init__(self, db, clock):
        self._db = db
        self._clock = clock
        MigrationRunner(db, "sm.economy",
                        _MIGRATIONS).run(clock)

    def _amount(self, amount) -> str:
        amt = _D(str(amount)).quantize(
            _D(_Q), rounding=_UP)
        if amt <= 0:
            raise ValueError(
                "amount positivo requerido")
        return str(amt)

    def assign_subsidy(self, *, student_id,
                       subsidy_type, amount,
                       reason="",
                       approved_by="") -> dict:
        if not str(subsidy_type).strip():
            raise ValueError(
                "subsidy_type requerido")
        sid = "SMSUB-" + str(uuid.uuid4())
        now = self._clock.now()
        with self._db.transaction() as cursor:
            cursor.execute(
                "INSERT INTO sm_subsidies"
                " (subsidy_id, student_id,"
                " subsidy_type, amount, reason,"
                " approved_by, created_at)"
                " VALUES (?, ?, ?, ?, ?, ?, ?)",
                (sid, student_id,
                 str(subsidy_type).strip(),
                 self._amount(amount),
                 str(reason),
                 str(approved_by), now))
        return {"subsidy_id": sid,
                "student_id": student_id,
                "subsidy_type":
                    str(subsidy_type).strip(),
                "amount": self._amount(amount)}

    def assign_bonus(self, *, student_id,
                     bonus_type, amount,
                     reason="",
                     approved_by="") -> dict:
        if not str(bonus_type).strip():
            raise ValueError(
                "bonus_type requerido")
        bid = "SMBON-" + str(uuid.uuid4())
        now = self._clock.now()
        with self._db.transaction() as cursor:
            cursor.execute(
                "INSERT INTO sm_bonuses"
                " (bonus_id, student_id,"
                " bonus_type, amount, reason,"
                " approved_by, created_at)"
                " VALUES (?, ?, ?, ?, ?, ?, ?)",
                (bid, student_id,
                 str(bonus_type).strip(),
                 self._amount(amount),
                 str(reason),
                 str(approved_by), now))
        return {"bonus_id": bid,
                "student_id": student_id,
                "bonus_type":
                    str(bonus_type).strip(),
                "amount": self._amount(amount)}

    def trace(self, student_id) -> List[dict]:
        subs = self._db.query_all(
            "SELECT * FROM sm_subsidies WHERE"
            " student_id = ? ORDER BY rowid",
            (student_id,))
        bons = self._db.query_all(
            "SELECT * FROM sm_bonuses WHERE"
            " student_id = ? ORDER BY rowid",
            (student_id,))
        out = []
        for r in subs:
            out.append({"kind": "SUBSIDY",
                        "id":
                            str(r["subsidy_id"]),
                        "type": str(
                            r["subsidy_type"]),
                        "amount":
                            str(r["amount"]),
                        "approved_by": str(
                            r["approved_by"]),
                        "created_at": float(
                            r["created_at"])})
        for r in bons:
            out.append({"kind": "BONUS",
                        "id":
                            str(r["bonus_id"]),
                        "type": str(
                            r["bonus_type"]),
                        "amount":
                            str(r["amount"]),
                        "approved_by": str(
                            r["approved_by"]),
                        "created_at": float(
                            r["created_at"])})
        out.sort(key=lambda x: x["created_at"])
        return out

    def total_aid(self, student_id) -> str:
        trace = self.trace(student_id)
        total = _D("0")
        for t in trace:
            total = total + _D(t["amount"])
        return str(total.quantize(_D(_Q)))
