
from __future__ import annotations

class GenerateAccountingReportUseCase:
    """Reporte contable del periodo: 3 estados."""

    def __init__(self, statements):
        self._st = statements

    def execute(self, *, company_id, period) -> dict:
        return {"report_type":
                    "ACCOUNTING_PERIOD_REPORT",
                "company_id": company_id,
                "period": period,
                "income_statement":
                    self._st.income_statement(
                        company_id, period),
                "balance_sheet":
                    self._st.balance_sheet(
                        company_id, period),
                "cash_flow": self._st.cash_flow(
                    company_id, period)}
