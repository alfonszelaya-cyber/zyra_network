
"""Policy Engine - politicas publicas (NG6). Ciclo
DRAFT -> ACTIVE -> SUSPENDED."""
from __future__ import annotations
from typing import List, Optional
import uuid
from shared_engines.common.clocks import Clock
from shared_engines.storage.database import Database
from shared_engines.storage.migrations import (
    Migration, MigrationRunner)

_MIGRATIONS = (
    Migration(1, "nexo_mg_policies", (
        "CREATE TABLE IF NOT EXISTS nexo_mg_policies (policy_id TEXT PRIMARY KEY, title TEXT NOT NULL, scope TEXT NOT NULL DEFAULT 'NATIONAL', status TEXT NOT NULL DEFAULT 'DRAFT', detail TEXT NOT NULL DEFAULT '', created_at REAL NOT NULL, updated_at REAL NOT NULL)",
    )),
)

class PolicyEngine:
    """Politicas publicas (ciclo de vida)."""

    def __init__(self, db, clock):
        self._db = db
        self._clock = clock
        MigrationRunner(db, "nexo.mgpolicy",
                        _MIGRATIONS).run(clock)

    def create_policy(self, *, title, scope="NATIONAL",
                      detail="") -> dict:
        pid = "POL-" + str(uuid.uuid4())
        now = self._clock.now()
        with self._db.transaction() as cursor:
            cursor.execute(
                "INSERT INTO nexo_mg_policies"
                " (policy_id, title, scope, status,"
                " detail, created_at, updated_at)"
                " VALUES (?, ?, ?, 'DRAFT', ?, ?, ?)",
                (pid, title, scope, detail, now,
                 now))
        return self.get_policy(pid)

    def get_policy(self,
                   policy_id) -> Optional[dict]:
        row = self._db.query_one(
            "SELECT * FROM nexo_mg_policies WHERE"
            " policy_id = ?", (policy_id,))
        if not row:
            return None
        return {"policy_id": str(row["policy_id"]),
                "title": str(row["title"]),
                "scope": str(row["scope"]),
                "status": str(row["status"]),
                "detail": str(row["detail"]),
                "updated_at":
                    float(row["updated_at"])}

    def _set(self, pid, status) -> dict:
        self._db.execute(
            "UPDATE nexo_mg_policies SET"
            " status = ?, updated_at = ? WHERE"
            " policy_id = ?",
            (status, self._clock.now(), pid))
        return self.get_policy(pid)

    def activate(self, policy_id) -> dict:
        return self._set(policy_id, "ACTIVE")

    def suspend(self, policy_id) -> dict:
        return self._set(policy_id, "SUSPENDED")

    def policies_of(self,
                    status="") -> List[dict]:
        if status:
            rows = self._db.query_all(
                "SELECT policy_id FROM"
                " nexo_mg_policies WHERE status = ?"
                " ORDER BY created_at", (status,))
        else:
            rows = self._db.query_all(
                "SELECT policy_id FROM"
                " nexo_mg_policies"
                " ORDER BY created_at")
        return [self.get_policy(
            str(r["policy_id"])) for r in rows]
