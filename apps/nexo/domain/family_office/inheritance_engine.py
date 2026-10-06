
"""Inheritance - NEXO / ZYRA (migrado mejorado)."""
from __future__ import annotations
from typing import Dict, List
import uuid
from shared_engines.common.clocks import Clock
from shared_engines.storage.database import Database
from shared_engines.storage.migrations import (
    Migration, MigrationRunner)

_MIGRATIONS = (
    Migration(1, "family_inheritances", (
        "CREATE TABLE IF NOT EXISTS family_inheritances (inheritance_id TEXT PRIMARY KEY, estate_name TEXT NOT NULL, beneficiaries_json TEXT NOT NULL DEFAULT '[]', total_value TEXT NOT NULL DEFAULT '0', status TEXT NOT NULL DEFAULT 'PLANNED', created_at REAL NOT NULL)",
    )),
)

class InheritanceEngine:
    """Gestion de herencias (persistente)."""

    def __init__(self, db, clock):
        self._db = db
        self._clock = clock
        MigrationRunner(db, "nexo.inheritance",
                        _MIGRATIONS).run(clock)

    def create_inheritance(self, *, estate_name,
                           beneficiaries, total_value):
        import json as _j
        iid = "INH-" + str(uuid.uuid4())
        now = self._clock.now()
        with self._db.transaction() as cursor:
            cursor.execute(
                "INSERT INTO family_inheritances"
                " (inheritance_id, estate_name,"
                " beneficiaries_json, total_value,"
                " status, created_at)"
                " VALUES (?, ?, ?, ?, 'PLANNED', ?)",
                (iid, estate_name,
                 _j.dumps(beneficiaries, default=str),
                 str(total_value), now))
        return {"inheritance_id": iid,
                "estate_name": estate_name,
                "beneficiaries": beneficiaries,
                "total_value": str(total_value),
                "status": "PLANNED"}

    def get_inheritances(self):
        import json as _j
        rows = self._db.query_all(
            "SELECT * FROM family_inheritances"
            " ORDER BY created_at")
        return [{"inheritance_id": str(r["inheritance_id"]),
                 "estate_name": str(r["estate_name"]),
                 "beneficiaries": _j.loads(
                     str(r["beneficiaries_json"])),
                 "total_value": str(r["total_value"]),
                 "status": str(r["status"])}
                for r in rows]
