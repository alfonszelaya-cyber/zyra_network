
from __future__ import annotations

class CloseAccountingPeriodUseCase:
    """Cierra el periodo con asiento de cierre."""

    def __init__(self, periods, statements, ledger):
        self._periods = periods
        self._st = statements
        self._ledger = ledger

    def execute(self, *, company_id, period,
                actor) -> dict:
        is_res = self._st.income_statement(
            company_id, period)
        ce = self._periods.closing_entry(
            company_id=company_id, period=period,
            ingresos=is_res["ingresos"],
            gastos=is_res["gastos"])
        posted = self._ledger.post_balanced(
            company_id=company_id, period=period,
            lines=ce["lines"],
            source_ref="PERIOD_CLOSE-" + period)
        closed = self._periods.close_period(
            company_id=company_id, period=period,
            actor=actor)
        return {"company_id": company_id,
                "period": period,
                "status": closed["status"],
                "closed_by": closed["closed_by"],
                "utilidad": ce["utilidad"],
                "closing_posted":
                    posted["posted"],
                "total_debit":
                    posted["total_debit"]}
