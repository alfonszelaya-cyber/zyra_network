
"""Public Metrics Engine - metricas publicas (NG6)."""
from __future__ import annotations
from typing import List, Optional
import uuid
from shared_engines.common.clocks import Clock
from shared_engines.storage.database import Database
from shared_engines.storage.migrations import (
    Migration, MigrationRunner)

_MIGRATIONS = (
    Migration(1, "nexo_mg_metrics", (
        "CREATE TABLE IF NOT EXISTS nexo_mg_metrics (metric_id TEXT PRIMARY KEY, name TEXT NOT NULL, period TEXT NOT NULL, value TEXT NOT NULL, unit TEXT NOT NULL DEFAULT '', source TEXT NOT NULL DEFAULT 'nexo', created_at REAL NOT NULL)",
    )),
)

class PublicMetricsEngine:
    """Metricas publicas publicadas."""

    def __init__(self, db, clock):
        self._db = db
        self._clock = clock
        MigrationRunner(db, "nexo.mgmetrics",
                        _MIGRATIONS).run(clock)

    def publish_metric(self, *, name, period,
                       value, unit="",
                       source="nexo") -> dict:
        mid = "MET-" + str(uuid.uuid4())
        now = self._clock.now()
        with self._db.transaction() as cursor:
            cursor.execute(
                "INSERT INTO nexo_mg_metrics"
                " (metric_id, name, period, value,"
                " unit, source, created_at)"
                " VALUES (?, ?, ?, ?, ?, ?, ?)",
                (mid, name, period, str(value),
                 unit, source, now))
        return {"metric_id": mid, "name": name,
                "period": period,
                "value": str(value),
                "unit": unit, "source": source}

    def metrics_of(self, name,
                   period="") -> List[dict]:
        if period:
            rows = self._db.query_all(
                "SELECT * FROM nexo_mg_metrics"
                " WHERE name = ? AND period = ?"
                " ORDER BY created_at",
                (name, period))
        else:
            rows = self._db.query_all(
                "SELECT * FROM nexo_mg_metrics"
                " WHERE name = ?"
                " ORDER BY created_at", (name,))
        return [{"metric_id":
                     str(r["metric_id"]),
                 "name": str(r["name"]),
                 "period": str(r["period"]),
                 "value": str(r["value"]),
                 "unit": str(r["unit"]),
                 "source": str(r["source"])}
                for r in rows]

    def latest(self, name) -> Optional[dict]:
        rows = self.metrics_of(name)
        return rows[-1] if rows else None
