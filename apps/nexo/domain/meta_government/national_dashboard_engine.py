
"""National Dashboard Engine - panel nacional (NG6).
Snapshot agregado; publica ejecucion como metrica."""
from __future__ import annotations
from typing import Dict
from shared_engines.common.clocks import Clock
from shared_engines.storage.database import Database

class NationalDashboardEngine:
    """Panel nacional agregado."""

    def __init__(self, db, clock, registry=None,
                 metrics=None):
        self._db = db
        self._clock = clock
        self._reg = registry
        self._met = metrics

    def snapshot(self, period="") -> Dict:
        institutions = (self._reg.institutions()
                        if self._reg is not None
                        else [])
        programs = (self._reg.all_programs()
                    if self._reg is not None
                    else [])
        total_b = 0.0
        total_p = 0.0
        for p in programs:
            total_b = total_b + float(
                p["budgeted"])
            total_p = total_p + float(p["paid"])
        exec_pct = (round(total_p * 100.0
                          / total_b, 2)
                    if total_b > 0 else 0.0)
        snap = {"period": period,
                "institutions":
                    len(institutions),
                "programs": len(programs),
                "total_budgeted":
                    f"{total_b:.2f}",
                "total_paid":
                    f"{total_p:.2f}",
                "national_execution_pct":
                    exec_pct,
                "generated_at":
                    self._clock.now()}
        if self._met is not None and period:
            self._met.publish_metric(
                name="national_execution_pct",
                period=period,
                value=str(exec_pct),
                unit="pct",
                source="national_dashboard")
        return snap
