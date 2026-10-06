
"""Cost Center Engine - centros de costo (NG3).
Reporte por centro, Decimal 2 decimales."""
from __future__ import annotations
from typing import List, Optional
import uuid
from shared_engines.common.clocks import Clock
from shared_engines.storage.database import Database
from shared_engines.storage.migrations import (
    Migration, MigrationRunner)

CENTER_TYPES = ("COST", "PROFIT", "DEPARTMENT",
                "PROJECT")

_MIGRATIONS = (
    Migration(1, "nexo_cost_centers", (
        "CREATE TABLE IF NOT EXISTS nexo_cost_centers (center_id TEXT PRIMARY KEY, company_id TEXT NOT NULL, center_code TEXT NOT NULL, center_name TEXT NOT NULL, center_type TEXT NOT NULL DEFAULT 'COST', active INTEGER NOT NULL DEFAULT 1, created_at REAL NOT NULL, UNIQUE(company_id, center_code))",
    )),
)

class CostCenterEngine:
    """Centros de costo/departamento/proyecto."""

    def __init__(self, db, clock):
        self._db = db
        self._clock = clock
        MigrationRunner(db, "nexo.costcenters",
                        _MIGRATIONS).run(clock)

    def create_center(self, *, company_id,
                      center_code, center_name,
                      center_type="COST") -> dict:
        if center_type not in CENTER_TYPES:
            center_type = "COST"
        cid = "CC-" + str(uuid.uuid4())
        now = self._clock.now()
        with self._db.transaction() as cursor:
            cursor.execute(
                "INSERT INTO nexo_cost_centers"
                " (center_id, company_id,"
                " center_code, center_name,"
                " center_type, active, created_at)"
                " VALUES (?, ?, ?, ?, ?, 1, ?)",
                (cid, company_id, center_code,
                 center_name, center_type, now))
        return {"center_id": cid,
                "company_id": company_id,
                "center_code": center_code,
                "center_name": center_name,
                "center_type": center_type,
                "active": True}

    def get_center(self, company_id,
                   center_code) -> Optional[dict]:
        row = self._db.query_one(
            "SELECT * FROM nexo_cost_centers WHERE"
            " company_id = ? AND center_code = ?",
            (company_id, center_code))
        if not row:
            return None
        return {"center_id": str(row["center_id"]),
                "center_code":
                    str(row["center_code"]),
                "center_name":
                    str(row["center_name"]),
                "center_type":
                    str(row["center_type"]),
                "active": bool(row["active"])}

    def centers_of(self, company_id) -> List[dict]:
        rows = self._db.query_all(
            "SELECT * FROM nexo_cost_centers WHERE"
            " company_id = ? ORDER BY center_code",
            (company_id,))
        return [{"center_id": str(r["center_id"]),
                 "center_code":
                     str(r["center_code"]),
                 "center_name":
                     str(r["center_name"]),
                 "center_type":
                     str(r["center_type"]),
                 "active": bool(r["active"])}
                for r in rows]

    def expenses_by_center(self, ledger,
                           company_id,
                           period) -> List[dict]:
        from decimal import Decimal as _D
        rows = ledger._db.query_all(
            "SELECT cost_center,"
            " COALESCE(SUM(debit),'0') AS d,"
            " COALESCE(SUM(credit),'0') AS c"
            " FROM nexo_gl_entries WHERE"
            " company_id = ? AND period = ?"
            " AND cost_center != ''"
            " GROUP BY cost_center",
            (company_id, period))
        return [{"cost_center": str(r["cost_center"]),
                 "debit": str(_D(str(r["d"]))
                           .quantize(_D("0.01"))),
                 "credit": str(_D(str(r["c"]))
                               .quantize(_D("0.01"))),
                 "neto": str((_D(str(r["d"]))
                              - _D(str(r["c"]))
                              ).quantize(_D("0.01")))}
                for r in rows]
