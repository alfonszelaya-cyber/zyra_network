
"""Government Compliance Engine - cumplimiento
regulatorio institucional (NG6). Informativo (regla
57: la Red informa, no censura)."""
from __future__ import annotations
from typing import List, Optional
import uuid
from shared_engines.common.clocks import Clock
from shared_engines.storage.database import Database
from shared_engines.storage.migrations import (
    Migration, MigrationRunner)

_MIGRATIONS = (
    Migration(1, "nexo_gov_compliance", (
        "CREATE TABLE IF NOT EXISTS nexo_gov_compliance (requirement_id TEXT PRIMARY KEY, institution_id TEXT NOT NULL, requirement TEXT NOT NULL, status TEXT NOT NULL DEFAULT 'PENDING', detail TEXT NOT NULL DEFAULT '', checked_at REAL, created_at REAL NOT NULL)",
    )),
)

class GovernmentComplianceEngine:
    """Requisitos de cumplimiento institucional."""

    def __init__(self, db, clock):
        self._db = db
        self._clock = clock
        MigrationRunner(db, "nexo.govcomp",
                        _MIGRATIONS).run(clock)

    def register_requirement(self, *,
                             institution_id,
                             requirement,
                             detail="") -> dict:
        rid = "GREQ-" + str(uuid.uuid4())
        now = self._clock.now()
        with self._db.transaction() as cursor:
            cursor.execute(
                "INSERT INTO"
                " nexo_gov_compliance"
                " (requirement_id,"
                " institution_id, requirement,"
                " status, detail, checked_at,"
                " created_at)"
                " VALUES (?, ?, ?, 'PENDING', ?,"
                " NULL, ?)",
                (rid, institution_id,
                 requirement, detail, now))
        return self.get_requirement(rid)

    def _set(self, rid, status) -> dict:
        self._db.execute(
            "UPDATE nexo_gov_compliance SET"
            " status = ?, checked_at = ? WHERE"
            " requirement_id = ?",
            (status, self._clock.now(), rid))
        return self.get_requirement(rid)

    def mark_compliant(self,
                       requirement_id) -> dict:
        return self._set(requirement_id,
                         "COMPLIANT")

    def mark_violation(self,
                       requirement_id) -> dict:
        return self._set(requirement_id,
                         "VIOLATION")

    def get_requirement(self,
                        requirement_id
                        ) -> Optional[dict]:
        row = self._db.query_one(
            "SELECT * FROM nexo_gov_compliance"
            " WHERE requirement_id = ?",
            (requirement_id,))
        if not row:
            return None
        return {"requirement_id":
                    str(row["requirement_id"]),
                "institution_id":
                    str(row["institution_id"]),
                "requirement":
                    str(row["requirement"]),
                "status": str(row["status"]),
                "detail": str(row["detail"]),
                "checked_at":
                    (float(row["checked_at"])
                     if row["checked_at"]
                     else None)}

    def requirements_of(self,
                        institution_id
                        ) -> List[dict]:
        rows = self._db.query_all(
            "SELECT requirement_id FROM"
            " nexo_gov_compliance WHERE"
            " institution_id = ?"
            " ORDER BY created_at",
            (institution_id,))
        return [self.get_requirement(
            str(r["requirement_id"]))
            for r in rows]

    def compliance_rate(self,
                        institution_id) -> dict:
        reqs = self.requirements_of(
            institution_id)
        total = len(reqs)
        ok = sum(1 for r in reqs
                 if r["status"] == "COMPLIANT")
        bad = sum(1 for r in reqs
                  if r["status"] == "VIOLATION")
        rate = (round(ok * 100.0 / total, 2)
                if total else 0.0)
        return {"institution_id":
                    institution_id,
                "total": total,
                "compliant": ok,
                "violations": bad,
                "compliance_rate_pct": rate}
