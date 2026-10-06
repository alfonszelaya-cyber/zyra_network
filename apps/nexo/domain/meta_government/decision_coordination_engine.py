
"""Decision Coordination Engine - decisiones publicas
(NG6) con opciones, analisis, decision (nivel 5
Coordinacion)."""
from __future__ import annotations
from typing import List, Optional
import json as _j
import uuid
from shared_engines.common.clocks import Clock
from shared_engines.storage.database import Database
from shared_engines.storage.migrations import (
    Migration, MigrationRunner)

_MIGRATIONS = (
    Migration(1, "nexo_mg_decisions", (
        "CREATE TABLE IF NOT EXISTS nexo_mg_decisions (decision_id TEXT PRIMARY KEY, title TEXT NOT NULL, options_json TEXT NOT NULL DEFAULT '[]', analysis TEXT NOT NULL DEFAULT '', chosen TEXT, status TEXT NOT NULL DEFAULT 'ANALYZING', created_at REAL NOT NULL, updated_at REAL NOT NULL)",
    )),
)

class DecisionCoordinationEngine:
    """Decisiones publicas con opciones y analisis."""

    def __init__(self, db, clock):
        self._db = db
        self._clock = clock
        MigrationRunner(db, "nexo.mgdecision",
                        _MIGRATIONS).run(clock)

    def propose_decision(self, *, title,
                         options) -> dict:
        did = "DEC-" + str(uuid.uuid4())
        now = self._clock.now()
        with self._db.transaction() as cursor:
            cursor.execute(
                "INSERT INTO nexo_mg_decisions"
                " (decision_id, title,"
                " options_json, analysis, chosen,"
                " status, created_at, updated_at)"
                " VALUES (?, ?, ?, '', NULL,"
                " 'ANALYZING', ?, ?)",
                (did, title,
                 _j.dumps(list(options),
                          default=str), now, now))
        return self.get_decision(did)

    def get_decision(self,
                     decision_id) -> Optional[dict]:
        row = self._db.query_one(
            "SELECT * FROM nexo_mg_decisions"
            " WHERE decision_id = ?",
            (decision_id,))
        if not row:
            return None
        return {"decision_id":
                    str(row["decision_id"]),
                "title": str(row["title"]),
                "options": _j.loads(
                    str(row["options_json"])),
                "analysis": str(row["analysis"]),
                "chosen": (str(row["chosen"])
                           if row["chosen"]
                           else None),
                "status": str(row["status"])}

    def record_analysis(self, *, decision_id,
                        analysis) -> dict:
        self._db.execute(
            "UPDATE nexo_mg_decisions SET"
            " analysis = ?, updated_at = ? WHERE"
            " decision_id = ?",
            (analysis, self._clock.now(),
             decision_id))
        return self.get_decision(decision_id)

    def decide(self, *, decision_id,
               chosen) -> dict:
        row = self._db.query_one(
            "SELECT status, options_json FROM"
            " nexo_mg_decisions WHERE"
            " decision_id = ?", (decision_id,))
        if not row:
            raise KeyError(decision_id)
        if str(row["status"]) == "DECIDED":
            raise ValueError("ya decidida")
        opts = _j.loads(str(row["options_json"]))
        if chosen not in opts:
            raise ValueError(
                "opcion no esta en las propuestas")
        self._db.execute(
            "UPDATE nexo_mg_decisions SET"
            " chosen = ?, status = 'DECIDED',"
            " updated_at = ? WHERE decision_id = ?",
            (chosen, self._clock.now(),
             decision_id))
        return self.get_decision(decision_id)

    def decisions_of(self,
                     status="") -> List[dict]:
        if status:
            rows = self._db.query_all(
                "SELECT decision_id FROM"
                " nexo_mg_decisions WHERE"
                " status = ? ORDER BY created_at",
                (status,))
        else:
            rows = self._db.query_all(
                "SELECT decision_id FROM"
                " nexo_mg_decisions ORDER BY"
                " created_at")
        return [self.get_decision(
            str(r["decision_id"]))
            for r in rows]
