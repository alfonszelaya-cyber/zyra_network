
"""Access Audit Engine - auditoria de accesos a
datos de estudiantes (SM9). Quien accedio a que
dato de quien, cuando y con que resultado."""
from __future__ import annotations
from typing import List
import uuid
from shared_engines.common.clocks import Clock
from shared_engines.storage.database import (
    Database)
from shared_engines.storage.migrations import (
    Migration, MigrationRunner)

_MIGRATIONS = (
    Migration(1, "sm_data_access_audit", (
        "CREATE TABLE IF NOT EXISTS sm_data_access_audit (audit_id TEXT PRIMARY KEY, actor TEXT NOT NULL, action TEXT NOT NULL, student_id TEXT NOT NULL, data_scope TEXT NOT NULL DEFAULT '', allowed INTEGER NOT NULL, detail TEXT NOT NULL DEFAULT '', created_at REAL NOT NULL)",
    )),
)

class AccessAuditEngine:
    """Auditoria de acceso a datos (persistente)."""

    def __init__(self, db, clock):
        self._db = db
        self._clock = clock
        MigrationRunner(db, "sm.accessaudit",
                        _MIGRATIONS).run(clock)

    def record(self, *, actor, action,
               student_id, allowed,
               data_scope="", detail="") -> dict:
        aid = "SMAAU-" + str(uuid.uuid4())
        now = self._clock.now()
        with self._db.transaction() as cursor:
            cursor.execute(
                "INSERT INTO"
                " sm_data_access_audit"
                " (audit_id, actor, action,"
                " student_id, data_scope, allowed,"
                " detail, created_at)"
                " VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
                (aid, str(actor), str(action),
                 student_id, str(data_scope),
                 1 if allowed else 0,
                 str(detail), now))
        return {"audit_id": aid,
                "actor": str(actor),
                "allowed": bool(allowed)}

    def history_of(self, student_id,
                   limit=200) -> List[dict]:
        rows = self._db.query_all(
            "SELECT * FROM"
            " sm_data_access_audit WHERE"
            " student_id = ? ORDER BY rowid"
            " DESC LIMIT ?", (student_id, limit))
        return [{"audit_id":
                     str(r["audit_id"]),
                 "actor": str(r["actor"]),
                 "action": str(r["action"]),
                 "allowed": bool(r["allowed"]),
                 "created_at":
                     float(r["created_at"])}
                for r in rows]
