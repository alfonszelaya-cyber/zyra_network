
"""Financial Validation Engine - validaciones
financieras (NG4). ID unico por fila."""
from __future__ import annotations
from typing import List
import uuid
from shared_engines.common.clocks import Clock
from shared_engines.storage.database import Database
from shared_engines.storage.migrations import (
    Migration, MigrationRunner)

_MIGRATIONS = (
    Migration(1, "nexo_finance_validations", (
        "CREATE TABLE IF NOT EXISTS nexo_finance_validations (validation_id TEXT PRIMARY KEY, subject TEXT NOT NULL, validation_type TEXT NOT NULL, passed INTEGER NOT NULL, detail TEXT NOT NULL DEFAULT '', validated_at REAL NOT NULL)",
    )),
)

class FinancialValidationEngine:
    """Validaciones financieras persistidas."""

    def __init__(self, db, clock,
                 supported_currencies=None):
        self._db = db
        self._clock = clock
        self._currencies = (supported_currencies
                            or ["USD", "EUR",
                                "GTQ", "SVC"])
        MigrationRunner(db, "nexo.finvalid",
                        _MIGRATIONS).run(clock)

    def validate_record(self, *, subject, amount,
                        currency="USD",
                        category="",
                        period="") -> dict:
        from decimal import Decimal as _D
        checks = []
        try:
            ok = _D(str(amount)) > 0
            detail = "monto=" + str(amount)
        except Exception:
            ok = False
            detail = "monto invalido"
        checks.append(("AMOUNT_POSITIVE", ok,
                       detail))
        checks.append(("CURRENCY_SUPPORTED",
                       currency in
                       self._currencies,
                       "currency=" + currency))
        checks.append(("CATEGORY_REQUIRED",
                       bool(str(category).strip()),
                       "category=" + category))
        checks.append(("PERIOD_REQUIRED",
                       bool(str(period).strip()),
                       "period=" + period))
        now = self._clock.now()
        ids = []
        with self._db.transaction() as cursor:
            for vtype, cok, cdetail in checks:
                vid = "FV-" + str(uuid.uuid4())
                cursor.execute(
                    "INSERT INTO"
                    " nexo_finance_validations"
                    " (validation_id, subject,"
                    " validation_type, passed,"
                    " detail, validated_at)"
                    " VALUES (?, ?, ?, ?, ?, ?)",
                    (vid, subject, vtype,
                     1 if cok else 0, cdetail,
                     now))
                ids.append(vid)
        failed = [c for c in checks if not c[1]]
        return {"validation_id":
                    ids[0] if ids else None,
                "row_ids": ids,
                "valid": len(failed) == 0,
                "checks": [{"check": c,
                            "passed": okk,
                            "detail": d}
                           for c, okk, d
                           in checks]}
