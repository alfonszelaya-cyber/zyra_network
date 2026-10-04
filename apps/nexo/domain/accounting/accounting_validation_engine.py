
# accounting_validation_engine.py - NEXO / ZYRA (migrado mejorado)
from __future__ import annotations

from decimal import Decimal
from typing import Dict, List

from shared_engines.common.clocks import Clock
from shared_engines.storage.database import Database
from shared_engines.storage.migrations import (
    Migration,
    MigrationRunner,
)

_MIGRATIONS = (
    Migration(1, "validation_history", (
        "CREATE TABLE IF NOT EXISTS validation_history ("
        " validation_id TEXT PRIMARY KEY,"
        " validation_type TEXT NOT NULL,"
        " result INTEGER NOT NULL,"
        " details_json TEXT NOT NULL,"
        " timestamp REAL NOT NULL)",
    )),
)


class AccountingValidationEngine:
    """Motor de validación contable (Decimal)."""

    def __init__(self, db: Database, clock: Clock) -> None:
        self._db = db
        self._clock = clock
        MigrationRunner(db, "nexo.validation",
                        _MIGRATIONS).run(clock)

    def _register(self, vtype: str, result: bool,
                  details: dict) -> None:
        import uuid as _u
        import json as _j
        now = self._clock.now()
        with self._db.transaction() as cursor:
            cursor.execute(
                "INSERT INTO validation_history"
                " (validation_id, validation_type,"
                " result, details_json, timestamp)"
                " VALUES (?, ?, ?, ?, ?)",
                (f"VAL-{_u.uuid4()}", vtype,
                 1 if result else 0,
                 _j.dumps(details, default=str), now))

    def validate_account_code(self, account_code: str) -> bool:
        result = bool(account_code
                      and len(account_code) >= 3)
        self._register("ACCOUNT_CODE", result,
                       {"account_code": account_code})
        return result

    def validate_amount(self, amount) -> bool:
        try:
            result = (Decimal(str(amount)) > 0)
        except Exception:
            result = False
        self._register("AMOUNT", result,
                       {"amount": str(amount)})
        return result

    def validate_entry_type(self, entry_type: str) -> bool:
        result = entry_type in ("DEBIT", "CREDIT")
        self._register("ENTRY_TYPE", result,
                       {"entry_type": entry_type})
        return result

    def validate_entry(self, entry: dict) -> Dict:
        errors = []
        if not self.validate_account_code(
                entry.get("account_code", "")):
            errors.append("INVALID_ACCOUNT_CODE")
        if not self.validate_amount(
                entry.get("amount", 0)):
            errors.append("INVALID_AMOUNT")
        if not self.validate_entry_type(
                entry.get("entry_type", "")):
            errors.append("INVALID_ENTRY_TYPE")
        result = {"valid": len(errors) == 0,
                  "errors": errors,
                  "validated_at": self._clock.now()}
        self._register("ACCOUNTING_ENTRY",
                       result["valid"], result)
        return result
