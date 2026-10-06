
from __future__ import annotations
from apps.nexo.domain.family_office.wealth_management_engine import (
    WealthManagementEngine)

class ManageWealthUseCase:
    def __init__(self, wealth_engine):
        self._engine = wealth_engine

    def execute(self, *, current_assets,
                current_liabilities,
                previous_assets="0") -> dict:
        snap = self._engine.generate_wealth_snapshot(
            total_assets=current_assets,
            total_liabilities=current_liabilities)
        growth = self._engine.calculate_growth(
            current_value=current_assets,
            previous_value=previous_assets)
        return {"snapshot": snap,
                "growth_pct": growth}
