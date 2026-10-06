
"""Collectibles Engine - coleccionables (NG9)."""
from __future__ import annotations
from typing import List, Optional
import uuid
from shared_engines.common.clocks import Clock
from shared_engines.storage.database import (
    Database)
from shared_engines.storage.migrations import (
    Migration, MigrationRunner)

_Q = "0.01"

_MIGRATIONS = (
    Migration(1, "nexo_fo_collectibles", (
        "CREATE TABLE IF NOT EXISTS nexo_fo_collectibles (asset_id TEXT PRIMARY KEY, company_id TEXT NOT NULL, name TEXT NOT NULL, value TEXT NOT NULL DEFAULT '0', category TEXT NOT NULL DEFAULT '', condition_grade TEXT NOT NULL DEFAULT '', status TEXT NOT NULL DEFAULT 'ACTIVE', created_at REAL NOT NULL)",
    )),
)

class CollectiblesEngine:
    """Coleccionables del family office."""

    def __init__(self, db, clock):
        self._db = db
        self._clock = clock
        MigrationRunner(db, "nexo.fo.col",
                        _MIGRATIONS).run(clock)

    def register(self, *, company_id, name,
                 value, category="",
                 condition_grade="") -> dict:
        from decimal import Decimal as _D
        val = _D(str(value)).quantize(_D(_Q))
        aid = "COL-" + str(uuid.uuid4())
        now = self._clock.now()
        with self._db.transaction() as cursor:
            cursor.execute(
                "INSERT INTO"
                " nexo_fo_collectibles"
                " (asset_id, company_id, name,"
                " value, category,"
                " condition_grade, status,"
                " created_at)"
                " VALUES (?, ?, ?, ?, ?, ?,"
                " 'ACTIVE', ?)",
                (aid, company_id, name,
                 str(val), str(category),
                 str(condition_grade), now))
        return self.get(aid)

    def _row(self, r) -> dict:
        from decimal import Decimal as _D
        return {"asset_id":
                    str(r["asset_id"]),
                "company_id":
                    str(r["company_id"]),
                "name": str(r["name"]),
                "value": str(_D(
                    str(r["value"])
                    ).quantize(_D(_Q))),
                "category":
                    str(r["category"]),
                "condition_grade":
                    str(r["condition_grade"]),
                "status": str(r["status"])}

    def get(self,
            asset_id) -> Optional[dict]:
        row = self._db.query_one(
            "SELECT * FROM"
            " nexo_fo_collectibles WHERE"
            " asset_id = ?", (asset_id,))
        return self._row(row) if row else None

    def list_for(self,
                 company_id) -> List[dict]:
        rows = self._db.query_all(
            "SELECT asset_id FROM"
            " nexo_fo_collectibles WHERE"
            " company_id = ?"
            " ORDER BY created_at",
            (company_id,))
        return [self.get(
            str(r["asset_id"]))
            for r in rows]

    def total_value(self,
                    company_id) -> str:
        from decimal import Decimal as _D
        rows = self._db.query_all(
            "SELECT value FROM"
            " nexo_fo_collectibles WHERE"
            " company_id = ? AND"
            " status = 'ACTIVE'",
            (company_id,))
        total = _D("0")
        for r in rows:
            total = (total
                     + _D(str(r["value"])))
        return str(total.quantize(_D(_Q)))

    def update_value(self, asset_id,
                     new_value) -> dict:
        from decimal import Decimal as _D
        val = _D(str(new_value)
                 ).quantize(_D(_Q))
        self._db.execute(
            "UPDATE nexo_fo_collectibles SET"
            " value = ? WHERE asset_id = ?",
            (str(val), asset_id))
        return self.get(asset_id)

    def deactivate(self, asset_id) -> dict:
        self._db.execute(
            "UPDATE nexo_fo_collectibles SET"
            " status = 'INACTIVE' WHERE"
            " asset_id = ?", (asset_id,))
        return self.get(asset_id)
