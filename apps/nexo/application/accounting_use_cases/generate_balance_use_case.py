
from __future__ import annotations
from decimal import Decimal as _D

class GenerateBalanceUseCase:
    """Balance de comprobacion + balance general.
    Totales 2 decimales; cuadrado bool nativo."""

    def __init__(self, ledger, chart,
                 statements=None):
        self._ledger = ledger
        self._chart = chart
        self._st = statements

    def execute(self, *, company_id, period) -> dict:
        tb = self._ledger.trial_balance(company_id,
                                        period)
        td = sum((_D(row["debit"])
                  for row in tb), _D("0"))
        tc = sum((_D(row["credit"])
                  for row in tb), _D("0"))
        td = td.quantize(_D("0.01"))
        tc = tc.quantize(_D("0.01"))
        result = {"company_id": company_id,
                  "period": period,
                  "trial_balance": tb,
                  "total_debit": str(td),
                  "total_credit": str(tc),
                  "cuadrado": td == tc}
        if self._st is not None:
            result["balance_sheet"] = (
                self._st.balance_sheet(company_id,
                                       period))
        return result
