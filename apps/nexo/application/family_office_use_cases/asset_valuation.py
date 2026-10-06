
from __future__ import annotations
from apps.nexo.domain.family_office.family_asset_engine import (
    FamilyAssetEngine)
from apps.nexo.domain.family_office.wealth_management_engine import (
    WealthManagementEngine)

class AssetValuationUseCase:
    """Valua el patrimonio familiar: suma activos
    y genera snapshot de patrimonio neto."""

    def __init__(self, asset_engine, wealth_engine):
        self._assets = asset_engine
        self._wealth = wealth_engine

    def execute(self, *, total_liabilities="0") -> dict:
        total = self._assets.calculate_total_assets()
        snap = self._wealth.generate_wealth_snapshot(
            total_assets=total,
            total_liabilities=total_liabilities)
        assets = self._assets.get_assets()
        return {"total_assets": str(total),
                "num_assets": len(assets),
                "assets": assets,
                "net_worth": snap["net_worth"],
                "status": "VALUED"}
