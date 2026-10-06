
from __future__ import annotations

class GenerateFinancialReportUseCase:
    """Reporte financiero del periodo."""

    def __init__(self, finance_engine,
                 budget_engine=None):
        self._eng = finance_engine
        self._bud = budget_engine

    def execute(self, *, company_id, period) -> dict:
        out = {"report_type":
                   "FINANCIAL_PERIOD_REPORT",
               "company_id": company_id,
               "period": period,
               "totals": self._eng.totals(
                   company_id, period),
               "records": self._eng.records_of(
                   company_id, period)}
        if self._bud is not None:
            out["budgets"] = self._bud.budgets_of(
                company_id, period)
            out["budget_alerts"] = (
                self._bud.alerts(company_id,
                                 period))
        return out
