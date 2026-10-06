
from __future__ import annotations

class ValidateFinancialOperationUseCase:
    """Validacion pura de operacion financiera."""

    def __init__(self, validation):
        self._val = validation

    def execute(self, *, amount, currency="USD",
                category="", period="") -> dict:
        return self._val.validate_record(
            subject="fin_operation_check",
            amount=amount, currency=currency,
            category=category, period=period)
