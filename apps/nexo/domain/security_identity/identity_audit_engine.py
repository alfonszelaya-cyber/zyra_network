
"""Nexo Identity Audit - auditoria de identidad (NG8)."""
from __future__ import annotations
from typing import List
import uuid
from shared_engines.common.clocks import Clock
from shared_engines.storage.database import Database
from shared_engines.storage.migrations import (
    Migration, MigrationRunner)

_MIGRATIONS = (
    Migration(1, "nexo_identity_audit", (
        "CREATE TABLE IF NOT EXISTS nexo_identity_audit (audit_id TEXT PRIMARY KEY, zid TEXT NOT NULL, action TEXT NOT NULL, actor TEXT NOT NULL DEFAULT '', detail TEXT NOT NULL DEFAULT '', created_at REAL NOT NULL)",
    )),
)

class NexoIdentityAudit:
    """Auditoria de identidad NEXO."""

    def __init__(self, db, clock):
        self._db = db
        self._clock = clock
        MigrationRunner(db, "nexo.idaudit",
                        _MIGRATIONS).run(clock)

    def record(self, *, zid, action, actor="",
               detail="") -> dict:
        aid = "IDA-" + str(uuid.uuid4())
        now = self._clock.now()
        with self._db.transaction() as cursor:
            cursor.execute(
                "INSERT INTO nexo_identity_audit"
                " (audit_id, zid, action, actor,"
                " detail, created_at)"
                " VALUES (?, ?, ?, ?, ?, ?)",
                (aid, zid, action, actor,
                 detail, now))
        return {"audit_id": aid, "zid": zid,
                "action": action,
                "created_at": now}

    def history_of(self, zid,
                   limit=100) -> List[dict]:
        rows = self._db.query_all(
            "SELECT * FROM nexo_identity_audit"
            " WHERE zid = ? ORDER BY created_at"
            " DESC LIMIT ?", (zid, limit))
        return [{"audit_id": str(r["audit_id"]),
                 "action": str(r["action"]),
                 "actor": str(r["actor"]),
                 "detail": str(r["detail"]),
                 "created_at":
                     float(r["created_at"])}
                for r in rows]
