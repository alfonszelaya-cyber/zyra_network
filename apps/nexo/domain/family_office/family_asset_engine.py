
"""Family Asset Engine - NEXO / ZYRA (migrado mejorado)."""
from __future__ import annotations
from typing import Dict, List, Optional
import uuid
from shared_engines.common.clocks import Clock
from shared_engines.storage.database import Database
from shared_engines.storage.migrations import (
    Migration, MigrationRunner)

_MIGRATIONS = (
    Migration(1, "family_assets", (
        "CREATE TABLE IF NOT EXISTS family_assets (asset_id TEXT PRIMARY KEY, asset_type TEXT NOT NULL, asset_name TEXT NOT NULL, value TEXT NOT NULL, jurisdiction TEXT NOT NULL DEFAULT '', metadata_json TEXT NOT NULL DEFAULT '{}', status TEXT NOT NULL DEFAULT 'ACTIVE', created_at REAL NOT NULL)",
    )),
)

class FamilyAssetEngine:
    """Gestion de activos patrimoniales (Decimal)."""

    def __init__(self, db, clock):
        self._db = db
        self._clock = clock
        MigrationRunner(db, "nexo.familyassets",
                        _MIGRATIONS).run(clock)

    def register_asset(self, *, asset_type, asset_name,
                       value, jurisdiction,
                       metadata=None):
        from decimal import Decimal as _D
        val = _D(str(value))
        aid = "AST-" + str(uuid.uuid4())
        now = self._clock.now()
        import json as _j
        with self._db.transaction() as cursor:
            cursor.execute(
                "INSERT INTO family_assets"
                " (asset_id, asset_type, asset_name,"
                " value, jurisdiction, metadata_json,"
                " status, created_at)"
                " VALUES (?, ?, ?, ?, ?, ?, 'ACTIVE', ?)",
                (aid, asset_type, asset_name, str(val),
                 jurisdiction,
                 _j.dumps(metadata or {}, default=str),
                 now))
        return {"asset_id": aid,
                "asset_type": asset_type,
                "asset_name": asset_name,
                "value": str(val),
                "jurisdiction": jurisdiction,
                "status": "ACTIVE"}

    def get_assets(self):
        rows = self._db.query_all(
            "SELECT * FROM family_assets"
            " ORDER BY created_at")
        return [{"asset_id": str(r["asset_id"]),
                 "asset_type": str(r["asset_type"]),
                 "asset_name": str(r["asset_name"]),
                 "value": str(r["value"]),
                 "jurisdiction": str(r["jurisdiction"]),
                 "status": str(r["status"])}
                for r in rows]

    def calculate_total_assets(self):
        from decimal import Decimal as _D
        rows = self._db.query_all(
            "SELECT value FROM family_assets"
            " WHERE status = 'ACTIVE'")
        total = _D("0")
        for r in rows:
            total = total + _D(str(r["value"]))
        return total
