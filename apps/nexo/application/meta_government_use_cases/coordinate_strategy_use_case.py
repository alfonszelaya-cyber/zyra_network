
from __future__ import annotations

class CoordinateStrategyUseCase:
    """Crea objetivo de estrategia y define avance."""

    def __init__(self, strategy):
        self._strat = strategy

    def execute(self, *, title, target_period,
                progress_pct=0) -> dict:
        o = self._strat.create_objective(
            title=title,
            target_period=target_period)
        if progress_pct:
            o = self._strat.update_progress(
                objective_id=o["objective_id"],
                progress_pct=progress_pct)
        return o
