
"""Nexo Sync Engine - log de sincronizaciones (NG7).
Corridas RUNNING -> COMPLETED/FAILED. Rechaza items
negativos y doble cierre. KeyError para IDs
inexistentes (convencion del sistema)."""
from __future__ import annotations
from typing import List, Optional
import uuid
from shared_engines.common.clocks import Clock
from shared_engines.storage.database import Database
from shared_engines.storage.migrations import (
    Migration, MigrationRunner)

_MIGRATIONS = (
    Migration(1, "nexo_sync_log", (
        "CREATE TABLE IF NOT EXISTS nexo_sync_log (sync_id TEXT PRIMARY KEY, source TEXT NOT NULL, status TEXT NOT NULL DEFAULT 'RUNNING', items_synced INTEGER NOT NULL DEFAULT 0, detail TEXT NOT NULL DEFAULT '', created_at REAL NOT NULL, completed_at REAL)",
    )),
)

class NexoSyncEngine:
    """Corridas de sincronizacion registradas."""

    def __init__(self, db, clock):
        self._db = db
        self._clock = clock
        MigrationRunner(db, "nexo.sync",
                        _MIGRATIONS).run(clock)

    def start_sync(self, source) -> dict:
        if not str(source).strip():
            raise ValueError(
                "source requerido")
        sid = "SYN-" + str(uuid.uuid4())
        now = self._clock.now()
        with self._db.transaction() as cursor:
            cursor.execute(
                "INSERT INTO nexo_sync_log"
                " (sync_id, source, status,"
                " items_synced, detail,"
                " created_at, completed_at)"
                " VALUES (?, ?, 'RUNNING', 0, '',"
                " ?, NULL)",
                (sid, source, now))
        return self.get_sync(sid)

    def get_sync(self, sync_id) -> Optional[dict]:
        row = self._db.query_one(
            "SELECT * FROM nexo_sync_log WHERE"
            " sync_id = ?", (sync_id,))
        if not row:
            return None
        return {"sync_id": str(row["sync_id"]),
                "source": str(row["source"]),
                "status": str(row["status"]),
                "items_synced":
                    int(row["items_synced"]),
                "detail": str(row["detail"]),
                "created_at":
                    float(row["created_at"]),
                "completed_at": (
                    float(row["completed_at"])
                    if row["completed_at"]
                    else None)}

    def complete(self, sync_id, items_synced,
                 detail="") -> dict:
        row = self._db.query_one(
            "SELECT status FROM nexo_sync_log"
            " WHERE sync_id = ?", (sync_id,))
        if not row:
            raise KeyError(sync_id)
        if str(row["status"]) != "RUNNING":
            raise ValueError("no esta RUNNING")
        items = int(items_synced)
        if items < 0:
            raise ValueError(
                "items no pueden ser negativos")
        self._db.execute(
            "UPDATE nexo_sync_log SET status ="
            " 'COMPLETED', items_synced = ?,"
            " detail = ?, completed_at = ? WHERE"
            " sync_id = ?",
            (items, detail,
             self._clock.now(), sync_id))
        return self.get_sync(sync_id)

    def fail(self, sync_id, detail="") -> dict:
        row = self._db.query_one(
            "SELECT status FROM nexo_sync_log"
            " WHERE sync_id = ?", (sync_id,))
        if not row:
            raise KeyError(sync_id)
        if str(row["status"]) != "RUNNING":
            raise ValueError("no esta RUNNING")
        self._db.execute(
            "UPDATE nexo_sync_log SET status ="
            " 'FAILED', detail = ?,"
            " completed_at = ? WHERE sync_id = ?",
            (detail, self._clock.now(),
             sync_id))
        return self.get_sync(sync_id)

    def last_sync(self, source) -> Optional[dict]:
        row = self._db.query_one(
            "SELECT sync_id FROM nexo_sync_log"
            " WHERE source = ?"
            " ORDER BY created_at DESC LIMIT 1",
            (source,))
        return (self.get_sync(
            str(row["sync_id"]))
            if row else None)

    def history(self, limit=50) -> List[dict]:
        rows = self._db.query_all(
            "SELECT sync_id FROM nexo_sync_log"
            " ORDER BY created_at DESC LIMIT ?",
            (limit,))
        return [self.get_sync(str(r["sync_id"]))
                for r in rows]
