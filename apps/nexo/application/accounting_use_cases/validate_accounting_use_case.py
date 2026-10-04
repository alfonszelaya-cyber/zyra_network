
from __future__ import annotations
from apps.nexo.domain.accounting.accounting_validation_engine import (
    AccountingValidationEngine)

class ValidateAccountingUseCase:
    def __init__(self, validation_engine:
                 AccountingValidationEngine) -> None:
        self._engine = validation_engine

    def execute(self, journal_entry: dict) -> dict:
        return self._engine.validate_entry(journal_entry)
