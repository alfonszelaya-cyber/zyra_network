
"""Financial Statements Engine - estados financieros
(NG3). Montos SIEMPRE con 2 decimales. cuadra bool
nativo."""
from __future__ import annotations
from typing import Dict, List
from shared_engines.common.clocks import Clock
from shared_engines.storage.database import Database

_Q = "0.01"

class FinancialStatementsEngine:
    """Estados financieros desde el mayor."""

    def __init__(self, db, clock,
                 chart=None, ledger=None,
                 treasury=None):
        self._db = db
        self._clock = clock
        self._chart = chart
        self._ledger = ledger
        self._treasury = treasury

    def income_statement(self, company_id,
                         period) -> Dict:
        from decimal import Decimal as _D
        ingresos = _D("0")
        gastos = _D("0")
        detalle = {"INCOME": [], "EXPENSE": []}
        if self._ledger is not None:
            for row in self._ledger.trial_balance(
                    company_id, period):
                acct = (self._chart.get_account(
                    company_id,
                    row["account_code"])
                    if self._chart else None)
                atype = (acct["account_type"]
                         if acct else "EXPENSE")
                if atype == "INCOME":
                    ingresos = (ingresos
                                + _D(row["credit"])
                                - _D(row["debit"]))
                    detalle["INCOME"].append(row)
                elif atype == "EXPENSE":
                    gastos = (gastos
                              + _D(row["debit"])
                              - _D(row["credit"]))
                    detalle["EXPENSE"].append(row)
        utilidad = ingresos - gastos
        q = lambda v: str(v.quantize(_D(_Q)))
        return {"statement": "INCOME_STATEMENT",
                "company_id": company_id,
                "period": period,
                "ingresos": q(ingresos),
                "gastos": q(gastos),
                "utilidad": q(utilidad),
                "detalle": detalle,
                "generated_at": self._clock.now()}

    def balance_sheet(self, company_id,
                      period) -> Dict:
        from decimal import Decimal as _D
        activos = _D("0")
        pasivos = _D("0")
        patrimonio = _D("0")
        is_res = self.income_statement(company_id,
                                       period)
        utilidad = _D(is_res["utilidad"])
        if self._ledger is not None:
            for row in self._ledger.trial_balance(
                    company_id, period):
                acct = (self._chart.get_account(
                    company_id,
                    row["account_code"])
                    if self._chart else None)
                atype = (acct["account_type"]
                         if acct else "")
                if atype == "ASSET":
                    activos = (activos
                               + _D(row["debit"])
                               - _D(row["credit"]))
                elif atype == "LIABILITY":
                    pasivos = (pasivos
                               + _D(row["credit"])
                               - _D(row["debit"]))
                elif atype == "EQUITY":
                    patrimonio = (patrimonio
                                  + _D(row["credit"])
                                  - _D(row["debit"]))
        patrimonio_total = patrimonio + utilidad
        q = lambda v: str(v.quantize(_D(_Q)))
        return {"statement": "BALANCE_SHEET",
                "company_id": company_id,
                "period": period,
                "activos": q(activos),
                "pasivos": q(pasivos),
                "patrimonio":
                    q(patrimonio_total),
                "utilidad_periodo": q(utilidad),
                "cuadra": (activos
                           == pasivos
                           + patrimonio_total),
                "generated_at": self._clock.now()}

    def cash_flow(self, company_id, period) -> Dict:
        from decimal import Decimal as _D
        entradas = _D("0")
        salidas = _D("0")
        if self._treasury is not None:
            tx = self._treasury.transactions_of(
                company_id, period)
            for t in tx:
                v = _D(t["amount"])
                if t["tx_type"] == "DEPOSIT":
                    entradas = entradas + v
                elif (t["tx_type"]
                      == "WITHDRAWAL"):
                    salidas = salidas + v
        q = lambda v: str(v.quantize(_D(_Q)))
        return {"statement": "CASH_FLOW",
                "company_id": company_id,
                "period": period,
                "entradas": q(entradas),
                "salidas": q(salidas),
                "neto": q(entradas - salidas),
                "generated_at": self._clock.now()}
