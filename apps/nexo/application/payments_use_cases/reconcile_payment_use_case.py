
from __future__ import annotations

class ReconcilePaymentUseCase:
    """Concilia statement externo contra pagos y marca
    RECONCILED los matcheados."""

    def __init__(self, reconciliation,
                 payment_engine=None):
        self._rec = reconciliation
        self._eng = payment_engine

    def execute(self, *, company_id, statement,
                payments=None) -> dict:
        if payments is None:
            payments = (self._eng.payments_for(
                company_id)
                if self._eng is not None else [])
        r = self._rec.reconcile(
            company_id=company_id, payments=payments,
            statement=statement)
        for item in r["items"]["matched"]:
            if (self._eng is not None
                    and item.get("payment_id")):
                self._eng.mark_reconciled(
                    item["payment_id"])
        return r
