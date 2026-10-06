
"""Governance Engine (SM5)."""
from __future__ import annotations
from typing import Dict, List
import uuid
from shared_engines.common.clocks import Clock
from shared_engines.storage.database import (
    Database)
from shared_engines.storage.migrations import (
    Migration, MigrationRunner)

_MIGRATIONS = (
    Migration(1, "sm_supervisions", (
        "CREATE TABLE IF NOT EXISTS sm_supervisions (supervision_id TEXT PRIMARY KEY, institution_id TEXT NOT NULL, supervisor TEXT NOT NULL, findings TEXT NOT NULL DEFAULT '', status TEXT NOT NULL DEFAULT 'OPEN', created_at REAL NOT NULL, closed_at REAL)",
    )),
    Migration(2, "sm_policies", (
        "CREATE TABLE IF NOT EXISTS sm_policies (policy_id TEXT PRIMARY KEY, title TEXT NOT NULL, scope TEXT NOT NULL DEFAULT 'NATIONAL', status TEXT NOT NULL DEFAULT 'DRAFT', detail TEXT NOT NULL DEFAULT '', created_at REAL NOT NULL)",
    )),
)

class GovernanceEngine:
    """Supervision escolar + politicas educativas."""

    def __init__(self, db, clock):
        self._db = db
        self._clock = clock
        MigrationRunner(db, "sm.governance",
                        _MIGRATIONS).run(clock)

    def supervise(self, *, institution_id,
                  supervisor,
                  findings="") -> dict:
        if not str(supervisor).strip():
            raise ValueError(
                "supervisor requerido")
        sid = "SMSUP-" + str(uuid.uuid4())
        now = self._clock.now()
        with self._db.transaction() as cursor:
            cursor.execute(
                "INSERT INTO sm_supervisions"
                " (supervision_id,"
                " institution_id, supervisor,"
                " findings, status, created_at)"
                " VALUES (?, ?, ?, ?, 'OPEN', ?)",
                (sid, institution_id,
                 str(supervisor).strip(),
                 str(findings), now))
        return {"supervision_id": sid,
                "institution_id":
                    institution_id,
                "supervisor":
                    str(supervisor).strip(),
                "status": "OPEN"}

    def close_supervision(self,
                          supervision_id) -> dict:
        self._db.execute(
            "UPDATE sm_supervisions SET"
            " status = 'CLOSED', closed_at = ?"
            " WHERE supervision_id = ?",
            (self._clock.now(),
             supervision_id))
        row = self._db.query_one(
            "SELECT * FROM sm_supervisions WHERE"
            " supervision_id = ?",
            (supervision_id,))
        if not row:
            raise KeyError(supervision_id)
        return {"supervision_id":
                    str(row["supervision_id"]),
                "status": str(row["status"])}

    def create_policy(self, *, title, scope="NATIONAL",
                      detail="") -> dict:
        if not str(title).strip():
            raise ValueError("title requerido")
        pid = "SMPOL-" + str(uuid.uuid4())
        now = self._clock.now()
        with self._db.transaction() as cursor:
            cursor.execute(
                "INSERT INTO sm_policies"
                " (policy_id, title, scope,"
                " status, detail, created_at)"
                " VALUES (?, ?, ?, 'DRAFT', ?, ?)",
                (pid, str(title).strip(), scope,
                 str(detail), now))
        return self.get_policy(pid)

    def get_policy(self, policy_id
                   ) -> Optional[dict]:
        row = self._db.query_one(
            "SELECT * FROM sm_policies WHERE"
            " policy_id = ?", (policy_id,))
        if not row:
            return None
        return {"policy_id":
                    str(row["policy_id"]),
                "title": str(row["title"]),
                "scope": str(row["scope"]),
                "status": str(row["status"]),
                "detail": str(row["detail"])}

    def activate_policy(self, policy_id) -> dict:
        self._db.execute(
            "UPDATE sm_policies SET status ="
            " 'ACTIVE' WHERE policy_id = ?",
            (policy_id,))
        return self.get_policy(policy_id)

    def ministry_dashboard(self, *,
                           registry,
                           enrollment_engine=None
                           ) -> Dict:
        """Snapshot nacional para MINED."""
        institutions = registry.list_all()
        total_enrolled = 0
        if enrollment_engine is not None:
            for inst in institutions:
                roster = (enrollment_engine.
                          roster(
                              inst["institution_id"],
                              "2026"))
                total_enrolled = (total_enrolled
                                  + len(roster))
        return {"dashboard": "MINISTRY_VIEW",
                "institutions":
                    len(institutions),
                "enrolled_2026":
                    total_enrolled,
                "generated_at":
                    self._clock.now()}
