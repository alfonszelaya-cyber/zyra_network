
from __future__ import annotations

class ProcessPaymentUseCase:
    """Valida -> registra pago -> emite evento NEXO_*."""

    def __init__(self, validation, payment_engine):
        self._val = validation
        self._eng = payment_engine

    def execute(self, *, company_id, direction,
                amount, currency="USD",
                counterparty="", reference="",
                method="") -> dict:
        v = self._val.validate_payment(
            amount=amount, currency=currency,
            counterparty=counterparty,
            reference=reference)
        if not v["valid"]:
            return {"processed": False,
                    "validation": v}
        p = self._eng.record_payment(
            company_id=company_id,
            direction=direction, amount=amount,
            currency=currency,
            counterparty=counterparty,
            reference=reference, method=method)
        return {"processed": True, "payment": p,
                "validation": v}
