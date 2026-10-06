
from __future__ import annotations
from apps.nexo.domain.family_office.world_heritage_engine import (
    WorldHeritageEngine)

class WorldHeritageManagementUseCase:
    def __init__(self, heritage_engine):
        self._engine = heritage_engine

    def execute(self, *, action: str,
                asset_name: str = "",
                asset_type: str = "",
                country: str = "",
                estimated_value: str = "0",
                heritage_id: str = "") -> dict:
        if action == "register":
            return self._engine.register_heritage_asset(
                asset_name=asset_name,
                asset_type=asset_type,
                country=country,
                estimated_value=estimated_value)
        if action == "summary":
            return self._engine.generate_summary()
        if action == "report":
            return self._engine.generate_report()
        return {"error": "unknown action"}
