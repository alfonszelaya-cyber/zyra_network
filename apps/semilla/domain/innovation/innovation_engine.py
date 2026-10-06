
"""Innovation Engine - startups y patentes (SM7)."""
from __future__ import annotations
from typing import List, Optional
import uuid
from shared_engines.common.clocks import Clock
from shared_engines.storage.database import (
    Database)
from shared_engines.storage.migrations import (
    Migration, MigrationRunner)

STARTUP_STAGES = ("IDEA", "INCUBATING", "LAUNCHED")
PATENT_STATUS = ("FILED", "UNDER_REVIEW",
                 "GRANTED", "REJECTED")

_MIGRATIONS = (
    Migration(1, "sm_startups", (
        "CREATE TABLE IF NOT EXISTS sm_startups (startup_id TEXT PRIMARY KEY, name TEXT NOT NULL, founder_student_id TEXT NOT NULL, stage TEXT NOT NULL DEFAULT 'IDEA', description TEXT NOT NULL DEFAULT '', created_at REAL NOT NULL, updated_at REAL NOT NULL)",
    )),
    Migration(2, "sm_patents", (
        "CREATE TABLE IF NOT EXISTS sm_patents (patent_id TEXT PRIMARY KEY, title TEXT NOT NULL, student_id TEXT NOT NULL, project_ref TEXT NOT NULL DEFAULT '', status TEXT NOT NULL DEFAULT 'FILED', created_at REAL NOT NULL, updated_at REAL NOT NULL)",
    )),
)

class InnovationEngine:
    """Startups y patentes estudiantiles."""

    def __init__(self, db, clock):
        self._db = db
        self._clock = clock
        MigrationRunner(db, "sm.innovation",
                        _MIGRATIONS).run(clock)

    def create_startup(self, *, name,
                       founder_student_id,
                       description="") -> dict:
        if not str(name).strip():
            raise ValueError("name requerido")
        sid = "SMSTU-" + str(uuid.uuid4())
        now = self._clock.now()
        with self._db.transaction() as cursor:
            cursor.execute(
                "INSERT INTO sm_startups"
                " (startup_id, name,"
                " founder_student_id, stage,"
                " description, created_at,"
                " updated_at)"
                " VALUES (?, ?, ?, 'IDEA', ?, ?, ?)",
                (sid, str(name).strip(),
                 founder_student_id,
                 str(description), now, now))
        return self.get_startup(sid)

    def get_startup(self, startup_id
                    ) -> Optional[dict]:
        row = self._db.query_one(
            "SELECT * FROM sm_startups WHERE"
            " startup_id = ?", (startup_id,))
        if not row:
            return None
        return {"startup_id":
                    str(row["startup_id"]),
                "name": str(row["name"]),
                "founder_student_id":
                    str(row["founder_student_id"]),
                "stage": str(row["stage"]),
                "description":
                    str(row["description"])}

    def advance_stage(self, startup_id) -> dict:
        s = self.get_startup(startup_id)
        if not s:
            raise KeyError(startup_id)
        order = list(STARTUP_STAGES)
        idx = order.index(s["stage"])
        if idx >= len(order) - 1:
            raise ValueError(
                "ya en etapa final")
        nxt = order[idx + 1]
        self._db.execute(
            "UPDATE sm_startups SET stage = ?,"
            " updated_at = ? WHERE startup_id = ?",
            (nxt, self._clock.now(), startup_id))
        return self.get_startup(startup_id)

    def file_patent(self, *, title, student_id,
                    project_ref="") -> dict:
        if not str(title).strip():
            raise ValueError("title requerido")
        pid = "SMPAT-" + str(uuid.uuid4())
        now = self._clock.now()
        with self._db.transaction() as cursor:
            cursor.execute(
                "INSERT INTO sm_patents"
                " (patent_id, title, student_id,"
                " project_ref, status, created_at,"
                " updated_at)"
                " VALUES (?, ?, ?, ?, 'FILED',"
                " ?, ?)",
                (pid, str(title).strip(),
                 student_id, str(project_ref),
                 now, now))
        return {"patent_id": pid,
                "title": str(title).strip(),
                "status": "FILED"}

    def update_patent(self, patent_id,
                      status) -> dict:
        if status not in PATENT_STATUS:
            raise ValueError("status invalido")
        self._db.execute(
            "UPDATE sm_patents SET status = ?,"
            " updated_at = ? WHERE patent_id = ?",
            (status, self._clock.now(),
             patent_id))
        row = self._db.query_one(
            "SELECT * FROM sm_patents WHERE"
            " patent_id = ?", (patent_id,))
        if not row:
            raise KeyError(patent_id)
        return {"patent_id":
                    str(row["patent_id"]),
                "title": str(row["title"]),
                "status": str(row["status"])}

    def startups_by_stage(self, stage
                           ) -> List[dict]:
        rows = self._db.query_all(
            "SELECT startup_id FROM sm_startups"
            " WHERE stage = ? ORDER BY created_at",
            (stage,))
        return [self.get_startup(
            str(r["startup_id"]))
            for r in rows]
