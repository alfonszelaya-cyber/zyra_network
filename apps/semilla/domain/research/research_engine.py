
"""Research Engine - investigacion (SM7)."""
from __future__ import annotations
from typing import List, Optional
import uuid
from shared_engines.common.clocks import Clock
from shared_engines.storage.database import (
    Database)
from shared_engines.storage.migrations import (
    Migration, MigrationRunner)

RESEARCH_STATUS = ("ACTIVE", "PUBLISHED",
                   "ARCHIVED")

_MIGRATIONS = (
    Migration(1, "sm_research", (
        "CREATE TABLE IF NOT EXISTS sm_research (research_id TEXT PRIMARY KEY, title TEXT NOT NULL, lead_student_id TEXT NOT NULL, area TEXT NOT NULL DEFAULT '', summary TEXT NOT NULL DEFAULT '', status TEXT NOT NULL DEFAULT 'ACTIVE', published_at REAL, created_at REAL NOT NULL, updated_at REAL NOT NULL)",
    )),
)

class ResearchEngine:
    """Investigacion estudiantil (persistente)."""

    def __init__(self, db, clock):
        self._db = db
        self._clock = clock
        MigrationRunner(db, "sm.research",
                        _MIGRATIONS).run(clock)

    def create_research(self, *, title,
                        lead_student_id,
                        area="",
                        summary="") -> dict:
        if not str(title).strip():
            raise ValueError("title requerido")
        rid = "SMRES-" + str(uuid.uuid4())
        now = self._clock.now()
        with self._db.transaction() as cursor:
            cursor.execute(
                "INSERT INTO sm_research"
                " (research_id, title,"
                " lead_student_id, area, summary,"
                " status, created_at, updated_at)"
                " VALUES (?, ?, ?, ?, ?, 'ACTIVE',"
                " ?, ?)",
                (rid, str(title).strip(),
                 lead_student_id, str(area),
                 str(summary), now, now))
        return self.get_research(rid)

    def get_research(self, research_id
                     ) -> Optional[dict]:
        row = self._db.query_one(
            "SELECT * FROM sm_research WHERE"
            " research_id = ?", (research_id,))
        if not row:
            return None
        return {"research_id":
                    str(row["research_id"]),
                "title": str(row["title"]),
                "lead_student_id":
                    str(row["lead_student_id"]),
                "area": str(row["area"]),
                "summary": str(row["summary"]),
                "status": str(row["status"])}

    def publish(self, research_id,
                final_summary="") -> dict:
        r = self.get_research(research_id)
        if not r:
            raise KeyError(research_id)
        if r["status"] != "ACTIVE":
            raise ValueError("no esta activa")
        self._db.execute(
            "UPDATE sm_research SET status ="
            " 'PUBLISHED', summary = CASE WHEN"
            " ? != '' THEN ? ELSE summary END,"
            " published_at = ?, updated_at = ?"
            " WHERE research_id = ?",
            (str(final_summary),
             str(final_summary),
             self._clock.now(),
             self._clock.now(), research_id))
        return self.get_research(research_id)

    def active_research(self) -> List[dict]:
        rows = self._db.query_all(
            "SELECT research_id FROM sm_research"
            " WHERE status = 'ACTIVE'"
            " ORDER BY created_at")
        return [self.get_research(
            str(r["research_id"]))
            for r in rows]
