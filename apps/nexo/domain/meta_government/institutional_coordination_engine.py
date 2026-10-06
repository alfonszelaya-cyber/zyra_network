
"""Institutional Coordination Engine - acuerdos
interinstitucionales de alto nivel (NG6)."""
from __future__ import annotations
from typing import List, Optional
import json as _j
import uuid
from shared_engines.common.clocks import Clock
from shared_engines.storage.database import Database
from shared_engines.storage.migrations import (
    Migration, MigrationRunner)

_MIGRATIONS = (
    Migration(1, "nexo_mg_agreements", (
        "CREATE TABLE IF NOT EXISTS nexo_mg_agreements (agreement_id TEXT PRIMARY KEY, institutions_json TEXT NOT NULL DEFAULT '[]', subject TEXT NOT NULL, status TEXT NOT NULL DEFAULT 'PROPOSED', created_at REAL NOT NULL, updated_at REAL NOT NULL)",
    )),
)

class InstitutionalCoordinationEngine:
    """Acuerdos interinstitucionales."""

    def __init__(self, db, clock):
        self._db = db
        self._clock = clock
        MigrationRunner(db, "nexo.mgcoord",
                        _MIGRATIONS).run(clock)

    def propose_agreement(self, *, institutions,
                          subject) -> dict:
        aid = "AGR-" + str(uuid.uuid4())
        now = self._clock.now()
        with self._db.transaction() as cursor:
            cursor.execute(
                "INSERT INTO nexo_mg_agreements"
                " (agreement_id,"
                " institutions_json, subject,"
                " status, created_at, updated_at)"
                " VALUES (?, ?, ?, 'PROPOSED',"
                " ?, ?)",
                (aid, _j.dumps(institutions),
                 subject, now, now))
        return self.get_agreement(aid)

    def get_agreement(self,
                      agreement_id) -> Optional[dict]:
        row = self._db.query_one(
            "SELECT * FROM nexo_mg_agreements"
            " WHERE agreement_id = ?",
            (agreement_id,))
        if not row:
            return None
        return {"agreement_id":
                    str(row["agreement_id"]),
                "institutions": _j.loads(
                    str(row["institutions_json"])),
                "subject": str(row["subject"]),
                "status": str(row["status"]),
                "updated_at":
                    float(row["updated_at"])}

    def _set(self, aid, status) -> dict:
        self._db.execute(
            "UPDATE nexo_mg_agreements SET"
            " status = ?, updated_at = ? WHERE"
            " agreement_id = ?",
            (status, self._clock.now(), aid))
        return self.get_agreement(aid)

    def activate(self, agreement_id) -> dict:
        return self._set(agreement_id, "ACTIVE")

    def end(self, agreement_id) -> dict:
        return self._set(agreement_id, "ENDED")

    def active_agreements(self) -> List[dict]:
        rows = self._db.query_all(
            "SELECT agreement_id FROM"
            " nexo_mg_agreements WHERE"
            " status = 'ACTIVE' ORDER BY"
            " created_at")
        return [self.get_agreement(
            str(r["agreement_id"]))
            for r in rows]
