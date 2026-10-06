
"""National Strategy Engine - objetivos nacionales
(NG6) con avance porcentual."""
from __future__ import annotations
from typing import List, Optional
import uuid
from shared_engines.common.clocks import Clock
from shared_engines.storage.database import Database
from shared_engines.storage.migrations import (
    Migration, MigrationRunner)

_MIGRATIONS = (
    Migration(1, "nexo_mg_objectives", (
        "CREATE TABLE IF NOT EXISTS nexo_mg_objectives (objective_id TEXT PRIMARY KEY, title TEXT NOT NULL, target_period TEXT NOT NULL, progress_pct REAL NOT NULL DEFAULT 0, status TEXT NOT NULL DEFAULT 'ACTIVE', created_at REAL NOT NULL)",
    )),
)

class NationalStrategyEngine:
    """Objetivos nacionales con avance."""

    def __init__(self, db, clock):
        self._db = db
        self._clock = clock
        MigrationRunner(db, "nexo.mgstrategy",
                        _MIGRATIONS).run(clock)

    def create_objective(self, *, title,
                         target_period) -> dict:
        oid = "OBJ-" + str(uuid.uuid4())
        now = self._clock.now()
        with self._db.transaction() as cursor:
            cursor.execute(
                "INSERT INTO nexo_mg_objectives"
                " (objective_id, title,"
                " target_period, progress_pct,"
                " status, created_at)"
                " VALUES (?, ?, ?, 0, 'ACTIVE', ?)",
                (oid, title, target_period, now))
        return self.get_objective(oid)

    def get_objective(self,
                      objective_id) -> Optional[dict]:
        row = self._db.query_one(
            "SELECT * FROM nexo_mg_objectives"
            " WHERE objective_id = ?",
            (objective_id,))
        if not row:
            return None
        return {"objective_id":
                    str(row["objective_id"]),
                "title": str(row["title"]),
                "target_period":
                    str(row["target_period"]),
                "progress_pct":
                    float(row["progress_pct"]),
                "status": str(row["status"])}

    def update_progress(self, *, objective_id,
                        progress_pct) -> dict:
        from decimal import Decimal as _D
        p = _D(str(progress_pct)).quantize(
            _D("0.01"))
        if p < 0 or p > 100:
            raise ValueError(
                "progreso entre 0 y 100")
        self._db.execute(
            "UPDATE nexo_mg_objectives SET"
            " progress_pct = ? WHERE"
            " objective_id = ?",
            (float(p), objective_id))
        return self.get_objective(objective_id)

    def objectives_of(self) -> List[dict]:
        rows = self._db.query_all(
            "SELECT objective_id FROM"
            " nexo_mg_objectives ORDER BY"
            " created_at")
        return [self.get_objective(
            str(r["objective_id"]))
            for r in rows]
