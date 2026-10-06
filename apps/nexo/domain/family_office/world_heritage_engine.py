
"""World Heritage - NEXO / ZYRA (migrado mejorado)."""
from __future__ import annotations
from typing import Dict, List, Optional
import uuid
from shared_engines.common.clocks import Clock
from shared_engines.storage.database import Database
from shared_engines.storage.migrations import (
    Migration, MigrationRunner)

_MIGRATIONS = (
    Migration(1, "world_heritage_assets", (
        "CREATE TABLE IF NOT EXISTS world_heritage_assets (heritage_id TEXT PRIMARY KEY, asset_name TEXT NOT NULL, asset_type TEXT NOT NULL, country TEXT NOT NULL, estimated_value TEXT NOT NULL DEFAULT '0', metadata_json TEXT NOT NULL DEFAULT '{}', status TEXT NOT NULL DEFAULT 'REGISTERED', created_at REAL NOT NULL)",
    )),
)

class WorldHeritageEngine:
    """Gestion de patrimonio mundial (persistente)."""

    def __init__(self, db, clock):
        self._db = db
        self._clock = clock
        MigrationRunner(db, "nexo.heritage",
                        _MIGRATIONS).run(clock)

    def register_heritage_asset(self, *, asset_name,
                                asset_type, country,
                                estimated_value,
                                metadata=None):
        import json as _j
        hid = "WH-" + str(uuid.uuid4())
        now = self._clock.now()
        with self._db.transaction() as cursor:
            cursor.execute(
                "INSERT INTO world_heritage_assets"
                " (heritage_id, asset_name, asset_type,"
                " country, estimated_value, metadata_json,"
                " status, created_at)"
                " VALUES (?, ?, ?, ?, ?, ?, 'REGISTERED', ?)",
                (hid, asset_name, asset_type, country,
                 str(estimated_value),
                 _j.dumps(metadata or {}, default=str),
                 now))
        return {"heritage_id": hid,
                "asset_name": asset_name,
                "asset_type": asset_type,
                "country": country,
                "estimated_value": str(estimated_value),
                "status": "REGISTERED"}

    def get_assets(self):
        import json as _j
        rows = self._db.query_all(
            "SELECT * FROM world_heritage_assets"
            " ORDER BY created_at")
        return [{"heritage_id": str(r["heritage_id"]),
                 "asset_name": str(r["asset_name"]),
                 "asset_type": str(r["asset_type"]),
                 "country": str(r["country"]),
                 "estimated_value": str(r["estimated_value"]),
                 "status": str(r["status"])}
                for r in rows]

    def calculate_total_value(self):
        from decimal import Decimal as _D
        rows = self._db.query_all(
            "SELECT estimated_value FROM"
            " world_heritage_assets")
        total = _D("0")
        for r in rows:
            total = total + _D(str(r["estimated_value"]))
        return total

    def generate_summary(self) -> Dict:
        assets = self.get_assets()
        return {"total_assets": len(assets),
                "total_value": str(
                    self.calculate_total_value()),
                "generated_at": self._clock.now()}

    def generate_report(self) -> Dict:
        return {"assets": self.get_assets(),
                "summary": self.generate_summary(),
                "report_type": "WORLD_HERITAGE",
                "generated_at": self._clock.now()}
