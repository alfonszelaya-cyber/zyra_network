
"""Government Validation Engine - validaciones de
registros gubernamentales (NG6). ID unico por fila."""
from __future__ import annotations
from typing import List
import uuid
from shared_engines.common.clocks import Clock
from shared_engines.storage.database import Database
from shared_engines.storage.migrations import (
    Migration, MigrationRunner)

_MIGRATIONS = (
    Migration(1, "nexo_gov_validations", (
        "CREATE TABLE IF NOT EXISTS nexo_gov_validations (validation_id TEXT PRIMARY KEY, subject TEXT NOT NULL, validation_type TEXT NOT NULL, passed INTEGER NOT NULL, detail TEXT NOT NULL DEFAULT '', validated_at REAL NOT NULL)",
    )),
)

class GovernmentValidationEngine:
    """Validaciones gubernamentales persistidas."""

    def __init__(self, db, clock):
        self._db = db
        self._clock = clock
        MigrationRunner(db, "nexo.govval",
                        _MIGRATIONS).run(clock)

    def validate_program(self, *, subject,
                         budgeted,
                         institution_id,
                         period) -> dict:
        from decimal import Decimal as _D
        checks = []
        try:
            ok = _D(str(budgeted)) > 0
            detail = "budgeted=" + str(budgeted)
        except Exception:
            ok = False
            detail = "presupuesto invalido"
        checks.append(("BUDGET_POSITIVE", ok,
                       detail))
        checks.append(("INSTITUTION_REQUIRED",
                       bool(str(institution_id)
                            .strip()),
                       "institution="
                       + str(institution_id)))
        checks.append(("PERIOD_REQUIRED",
                       bool(str(period).strip()),
                       "period=" + str(period)))
        now = self._clock.now()
        ids = []
        with self._db.transaction() as cursor:
            for vtype, cok, cdetail in checks:
                vid = "GV-" + str(uuid.uuid4())
                cursor.execute(
                    "INSERT INTO"
                    " nexo_gov_validations"
                    " (validation_id, subject,"
                    " validation_type, passed,"
                    " detail, validated_at)"
                    " VALUES (?, ?, ?, ?, ?, ?)",
                    (vid, subject, vtype,
                     1 if cok else 0, cdetail,
                     now))
                ids.append(vid)
        failed = [c for c in checks if not c[1]]
        return {"row_ids": ids,
                "valid": len(failed) == 0,
                "checks": [{"check": c,
                            "passed": okk,
                            "detail": d}
                           for c, okk, d
                           in checks]}
