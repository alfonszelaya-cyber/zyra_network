
"""Nexo Report Registry - agregados de reportes."""
from __future__ import annotations
from typing import Dict
from shared_engines.common.clocks import Clock
from shared_engines.storage.database import Database

class NexoReportRegistry:
    """Agregados de reportes generados."""

    def __init__(self, db, clock):
        self._db = db
        self._clock = clock

    def counts_by_type(self) -> Dict[str, int]:
        rows = self._db.query_all(
            "SELECT report_type, COUNT(*) AS c"
            " FROM nexo_reports GROUP BY"
            " report_type")
        return {str(r["report_type"]): int(r["c"])
                for r in rows}

    def total(self) -> int:
        row = self._db.query_one(
            "SELECT COUNT(*) AS c FROM"
            " nexo_reports")
        return int(row["c"]) if row else 0
