
from __future__ import annotations

class ReconcileAccountsUseCase:
    """Conciliacion mayor vs saldos esperados."""

    def __init__(self, ledger):
        self._ledger = ledger

    def execute(self, *, company_id, period,
                expected_balances) -> dict:
        items = []
        ok_count = 0
        for acct, expected in (
                expected_balances.items()):
            real = self._ledger.account_balance(
                company_id, acct, period)
            match = (real["balance"]
                     == str(expected))
            if match:
                ok_count = ok_count + 1
            items.append({
                "account_code": acct,
                "expected": str(expected),
                "book_balance":
                    real["balance"],
                "matched": match})
        return {"company_id": company_id,
                "period": period,
                "reconciled": ok_count,
                "total": len(items),
                "all_matched":
                    ok_count == len(items),
                "items": items}
