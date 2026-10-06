
from __future__ import annotations

class ValidatePaymentUseCase:
    """Validacion pura de un pago (sin registrar)."""

    def __init__(self, validation):
        self._val = validation

    def execute(self, *, amount, currency="USD",
                counterparty="", reference="") -> dict:
        return self._val.validate_payment(
            amount=amount, currency=currency,
            counterparty=counterparty,
            reference=reference)
