
"""Nexo Identity Registry - usuarios NEXO <-> ZID
(regla 63: referencias)."""
from __future__ import annotations
from typing import List, Optional
import uuid
from shared_engines.common.clocks import Clock
from shared_engines.storage.database import Database
from shared_engines.storage.migrations import (
    Migration, MigrationRunner)

_MIGRATIONS = (
    Migration(1, "nexo_identity_registry", (
        "CREATE TABLE IF NOT EXISTS nexo_identity_registry (zid TEXT PRIMARY KEY, app_ref TEXT NOT NULL DEFAULT '', display_name TEXT NOT NULL DEFAULT '', status TEXT NOT NULL DEFAULT 'ACTIVE', created_at REAL NOT NULL)",
    )),
)

class NexoIdentityRegistry:
    """Usuarios NEXO <-> ZID (referencias)."""

    def __init__(self, db, clock):
        self._db = db
        self._clock = clock
        MigrationRunner(db, "nexo.idreg",
                        _MIGRATIONS).run(clock)

    def register(self, *, zid, app_ref="",
                 display_name="") -> dict:
        if not str(zid).strip():
            raise ValueError("zid requerido")
        now = self._clock.now()
        with self._db.transaction() as cursor:
            cursor.execute(
                "INSERT INTO"
                " nexo_identity_registry"
                " (zid, app_ref, display_name,"
                " status, created_at)"
                " VALUES (?, ?, ?, 'ACTIVE', ?)"
                " ON CONFLICT(zid) DO UPDATE SET"
                " app_ref = excluded.app_ref,"
                " display_name ="
                " excluded.display_name",
                (zid, app_ref, display_name,
                 now))
        return self.get(zid)

    def get(self, zid) -> Optional[dict]:
        row = self._db.query_one(
            "SELECT * FROM nexo_identity_registry"
            " WHERE zid = ?", (zid,))
        if not row:
            return None
        return {"zid": str(row["zid"]),
                "app_ref": str(row["app_ref"]),
                "display_name":
                    str(row["display_name"]),
                "status": str(row["status"]),
                "created_at":
                    float(row["created_at"])}

    def deactivate(self, zid) -> dict:
        self._db.execute(
            "UPDATE nexo_identity_registry SET"
            " status = 'INACTIVE' WHERE zid = ?",
            (zid,))
        return self.get(zid)

    def all(self) -> List[dict]:
        rows = self._db.query_all(
            "SELECT zid FROM"
            " nexo_identity_registry"
            " ORDER BY created_at")
        return [self.get(str(r["zid"]))
                for r in rows]
