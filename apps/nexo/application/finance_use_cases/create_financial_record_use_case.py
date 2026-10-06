
from __future__ import annotations

class CreateFinancialRecordUseCase:
    """Valida y crea registro financiero + traza."""

    def __init__(self, validation, finance_engine,
                 registry=None):
        self._val = validation
        self._eng = finance_engine
        self._reg = registry

    def execute(self, *, company_id, period,
                record_type, amount, category="",
                currency="USD",
                description="", actor="") -> dict:
        v = self._val.validate_record(
            subject="finance_record",
            amount=amount, currency=currency,
            category=category, period=period)
        if not v["valid"]:
            return {"created": False,
                    "validation": v}
        r = self._eng.create_record(
            company_id=company_id, period=period,
            record_type=record_type,
            amount=amount, category=category,
            currency=currency,
            description=description)
        if self._reg is not None:
            self._reg.log_event(
                company_id=company_id,
                event_type="RECORD_CREATED",
                payload=r, actor=actor)
        return {"created": True, "record": r}
