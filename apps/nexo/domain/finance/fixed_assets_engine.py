
"""Fixed Assets Engine - activos fijos (NG4).
Depreciacion lineal con tope. Montos 2 decimales."""
from __future__ import annotations
from typing import List, Optional
import uuid
from shared_engines.common.clocks import Clock
from shared_engines.storage.database import Database
from shared_engines.storage.migrations import (
    Migration, MigrationRunner)

_Q = "0.01"

_MIGRATIONS = (
    Migration(1, "nexo_fixed_assets", (
        "CREATE TABLE IF NOT EXISTS nexo_fixed_assets (asset_id TEXT PRIMARY KEY, company_id TEXT NOT NULL, asset_name TEXT NOT NULL, asset_code TEXT NOT NULL DEFAULT '', acquisition_cost TEXT NOT NULL, residual_value TEXT NOT NULL DEFAULT '0', useful_life_months INTEGER NOT NULL, accumulated_depreciation TEXT NOT NULL DEFAULT '0', currency TEXT NOT NULL DEFAULT 'USD', status TEXT NOT NULL DEFAULT 'ACTIVE', acquired_at REAL NOT NULL, created_at REAL NOT NULL)",
    )),
)

class FixedAssetsEngine:
    """Activos fijos + depreciacion lineal."""

    def __init__(self, db, clock):
        self._db = db
        self._clock = clock
        MigrationRunner(db, "nexo.fixedassets",
                        _MIGRATIONS).run(clock)

    def register_asset(self, *, company_id,
                       asset_name, acquisition_cost,
                       useful_life_months,
                       residual_value="0",
                       asset_code="",
                       currency="USD") -> dict:
        from decimal import Decimal as _D
        cost = _D(str(acquisition_cost)).quantize(
            _D(_Q))
        res = _D(str(residual_value)).quantize(
            _D(_Q))
        if cost <= 0:
            raise ValueError("costo positivo")
        if useful_life_months <= 0:
            raise ValueError("vida util > 0")
        if res >= cost:
            raise ValueError(
                "residual menor que costo")
        aid = "FA-" + str(uuid.uuid4())
        now = self._clock.now()
        with self._db.transaction() as cursor:
            cursor.execute(
                "INSERT INTO nexo_fixed_assets"
                " (asset_id, company_id, asset_name,"
                " asset_code, acquisition_cost,"
                " residual_value,"
                " useful_life_months,"
                " accumulated_depreciation,"
                " currency, status, acquired_at,"
                " created_at)"
                " VALUES (?, ?, ?, ?, ?, ?, ?, '0',"
                " ?, 'ACTIVE', ?, ?)",
                (aid, company_id, asset_name,
                 asset_code, str(cost), str(res),
                 int(useful_life_months), currency,
                 now, now))
        return {"asset_id": aid,
                "company_id": company_id,
                "asset_name": asset_name,
                "acquisition_cost": str(cost),
                "residual_value": str(res),
                "useful_life_months":
                    int(useful_life_months),
                "book_value": str(cost),
                "status": "ACTIVE"}

    def get_asset(self, asset_id) -> Optional[dict]:
        from decimal import Decimal as _D
        row = self._db.query_one(
            "SELECT * FROM nexo_fixed_assets WHERE"
            " asset_id = ?", (asset_id,))
        if not row:
            return None
        cost = _D(str(row["acquisition_cost"]))
        dep = _D(str(row["accumulated_depreciation"])
                 ).quantize(_D(_Q))
        return {"asset_id": str(row["asset_id"]),
                "company_id":
                    str(row["company_id"]),
                "asset_name":
                    str(row["asset_name"]),
                "acquisition_cost": str(cost),
                "residual_value":
                    str(row["residual_value"]),
                "useful_life_months":
                    int(row["useful_life_months"]),
                "accumulated_depreciation":
                    str(dep),
                "book_value": str(
                    (cost - dep).quantize(_D(_Q))),
                "status": str(row["status"])}

    def monthly_depreciation(self,
                             asset_id) -> str:
        from decimal import Decimal as _D
        row = self._db.query_one(
            "SELECT acquisition_cost, residual_value,"
            " useful_life_months FROM"
            " nexo_fixed_assets WHERE asset_id = ?",
            (asset_id,))
        if not row:
            raise KeyError(asset_id)
        dep = ((_D(str(row["acquisition_cost"]))
                - _D(str(row["residual_value"])))
               / _D(str(row["useful_life_months"])))
        return str(dep.quantize(_D(_Q)))

    def apply_month(self, asset_id,
                    months=1) -> dict:
        from decimal import Decimal as _D
        row = self._db.query_one(
            "SELECT acquisition_cost, residual_value,"
            " useful_life_months,"
            " accumulated_depreciation FROM"
            " nexo_fixed_assets WHERE asset_id = ?",
            (asset_id,))
        if not row:
            raise KeyError(asset_id)
        dep_m = ((_D(str(row["acquisition_cost"]))
                  - _D(str(row["residual_value"])))
                 / _D(str(row["useful_life_months"]))
                 ).quantize(_D(_Q))
        max_dep = (_D(str(row["acquisition_cost"]))
                   - _D(str(row["residual_value"]))
                   ).quantize(_D(_Q))
        cur = _D(str(row["accumulated_depreciation"]))
        new_dep = min(cur + (dep_m * _D(str(months))),
                      max_dep).quantize(_D(_Q))
        self._db.execute(
            "UPDATE nexo_fixed_assets SET"
            " accumulated_depreciation = ? WHERE"
            " asset_id = ?", (str(new_dep),
                              asset_id))
        return self.get_asset(asset_id)

    def dispose(self, *, asset_id, reason="") -> dict:
        self._db.execute(
            "UPDATE nexo_fixed_assets SET"
            " status = 'DISPOSED' WHERE"
            " asset_id = ?", (asset_id,))
        a = self.get_asset(asset_id)
        a["dispose_reason"] = reason
        return a

    def assets_of(self, company_id,
                  status="") -> List[dict]:
        if status:
            rows = self._db.query_all(
                "SELECT asset_id FROM"
                " nexo_fixed_assets WHERE"
                " company_id = ? AND status = ?",
                (company_id, status))
        else:
            rows = self._db.query_all(
                "SELECT asset_id FROM"
                " nexo_fixed_assets WHERE"
                " company_id = ?", (company_id,))
        return [self.get_asset(str(r["asset_id"]))
                for r in rows]
