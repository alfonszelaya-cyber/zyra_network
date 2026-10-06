
from __future__ import annotations
from apps.nexo.domain.family_office.family_asset_engine import (
    FamilyAssetEngine)

class RegisterFamilyAssetUseCase:
    def __init__(self, asset_engine):
        self._engine = asset_engine

    def execute(self, *, asset_type, asset_name,
                value, jurisdiction,
                metadata=None) -> dict:
        asset = self._engine.register_asset(
            asset_type=asset_type,
            asset_name=asset_name,
            value=value,
            jurisdiction=jurisdiction,
            metadata=metadata)
        total = self._engine.calculate_total_assets()
        return {"asset": asset,
                "portfolio_total": str(total)}
