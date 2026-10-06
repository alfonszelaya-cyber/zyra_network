
"""Nexo Report Engine - reportes formales (NG7)."""
from __future__ import annotations
from typing import List, Optional
import json as _j
import uuid
from shared_engines.common.clocks import Clock
from shared_engines.storage.database import Database
from shared_engines.storage.migrations import (
    Migration, MigrationRunner)

_MIGRATIONS = (
    Migration(1, "nexo_reports", (
        "CREATE TABLE IF NOT EXISTS nexo_reports (report_id TEXT PRIMARY KEY, report_type TEXT NOT NULL, company_id TEXT NOT NULL DEFAULT '', period TEXT NOT NULL DEFAULT '', payload_json TEXT NOT NULL DEFAULT '{}', created_at REAL NOT NULL)",
    )),
)

class NexoReportEngine:
    """Reportes formales persistidos."""

    def __init__(self, db, clock):
        self._db = db
        self._clock = clock
        MigrationRunner(db, "nexo.reports",
                        _MIGRATIONS).run(clock)

    def generate(self, *, report_type,
                 company_id="", period="",
                 data=None) -> dict:
        if not str(report_type).strip():
            raise ValueError(
                "report_type requerido")
        if data is None or not isinstance(
                data, dict):
            raise ValueError(
                "data requerida (objeto)")
        rid = "RPT-" + str(uuid.uuid4())
        now = self._clock.now()
        payload = {"report_id": rid,
                   "report_type": report_type,
                   "company_id": company_id,
                   "period": period,
                   "data": data,
                   "generated_at": now}
        with self._db.transaction() as cursor:
            cursor.execute(
                "INSERT INTO nexo_reports"
                " (report_id, report_type,"
                " company_id, period,"
                " payload_json, created_at)"
                " VALUES (?, ?, ?, ?, ?, ?)",
                (rid, report_type, company_id,
                 period,
                 _j.dumps(payload,
                          default=str), now))
        return payload

    def get(self, report_id) -> Optional[dict]:
        row = self._db.query_one(
            "SELECT payload_json FROM"
            " nexo_reports WHERE report_id = ?",
            (report_id,))
        if not row:
            return None
        return _j.loads(str(row["payload_json"]))

    def list_of(self, company_id,
                period="") -> List[dict]:
        if period:
            rows = self._db.query_all(
                "SELECT payload_json FROM"
                " nexo_reports WHERE"
                " company_id = ? AND period = ?"
                " ORDER BY created_at",
                (company_id, period))
        else:
            rows = self._db.query_all(
                "SELECT payload_json FROM"
                " nexo_reports WHERE"
                " company_id = ?"
                " ORDER BY created_at",
                (company_id,))
        return [_j.loads(str(r["payload_json"]))
                for r in rows]
