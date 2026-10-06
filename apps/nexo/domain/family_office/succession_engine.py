
"""Succession - NEXO / ZYRA (migrado mejorado)."""
from __future__ import annotations
from typing import Dict, List
import uuid
from shared_engines.common.clocks import Clock
from shared_engines.storage.database import Database
from shared_engines.storage.migrations import (
    Migration, MigrationRunner)

_MIGRATIONS = (
    Migration(1, "family_successions", (
        "CREATE TABLE IF NOT EXISTS family_successions (plan_id TEXT PRIMARY KEY, title TEXT NOT NULL, successors_json TEXT NOT NULL DEFAULT '[]', assets_json TEXT NOT NULL DEFAULT '[]', status TEXT NOT NULL DEFAULT 'ACTIVE', created_at REAL NOT NULL)",
    )),
)

class SuccessionEngine:
    """Planificacion sucesoria (persistente)."""

    def __init__(self, db, clock):
        self._db = db
        self._clock = clock
        MigrationRunner(db, "nexo.succession",
                        _MIGRATIONS).run(clock)

    def create_plan(self, *, title, successors, assets):
        import json as _j
        pid = "SUC-" + str(uuid.uuid4())
        now = self._clock.now()
        with self._db.transaction() as cursor:
            cursor.execute(
                "INSERT INTO family_successions"
                " (plan_id, title, successors_json,"
                " assets_json, status, created_at)"
                " VALUES (?, ?, ?, ?, 'ACTIVE', ?)",
                (pid, title,
                 _j.dumps(successors, default=str),
                 _j.dumps(assets, default=str), now))
        return {"plan_id": pid, "title": title,
                "successors": successors,
                "assets": assets, "status": "ACTIVE"}

    def get_plans(self):
        import json as _j
        rows = self._db.query_all(
            "SELECT * FROM family_successions"
            " ORDER BY created_at")
        return [{"plan_id": str(r["plan_id"]),
                 "title": str(r["title"]),
                 "successors": _j.loads(
                     str(r["successors_json"])),
                 "assets": _j.loads(str(r["assets_json"])),
                 "status": str(r["status"])}
                for r in rows]
