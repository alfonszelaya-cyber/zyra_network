
from __future__ import annotations

class ProcessFinancialOperationUseCase:
    """Operacion financiera completa."""

    def __init__(self, validation, finance_engine,
                 treasury=None, budget=None):
        self._val = validation
        self._eng = finance_engine
        self._trs = treasury
        self._bud = budget

    def execute(self, *, company_id, period,
                record_type, amount, category="",
                currency="USD",
                treasury_account="",
                reference="", actor="") -> dict:
        v = self._val.validate_record(
            subject="fin_operation",
            amount=amount, currency=currency,
            category=category, period=period)
        if not v["valid"]:
            return {"processed": False,
                    "validation": v}
        rec = self._eng.create_record(
            company_id=company_id, period=period,
            record_type=record_type,
            amount=amount, category=category,
            currency=currency)
        treasury_tx = None
        if (self._trs is not None
                and treasury_account):
            if record_type == "INCOME":
                treasury_tx = self._trs.deposit(
                    account_id=treasury_account,
                    amount=amount,
                    reference=reference)
            elif record_type == "EXPENSE":
                treasury_tx = self._trs.withdraw(
                    account_id=treasury_account,
                    amount=amount,
                    reference=reference)
        budget_upd = None
        if (self._bud is not None and category
                and record_type == "EXPENSE"):
            budget_upd = self._bud.register_actual(
                company_id=company_id,
                period=period, category=category,
                amount=amount)
        return {"processed": True,
                "record": rec,
                "treasury_tx": treasury_tx,
                "budget": budget_upd}
