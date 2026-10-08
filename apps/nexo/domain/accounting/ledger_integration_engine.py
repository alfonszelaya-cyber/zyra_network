
"""Ledger Integration Engine (N-2..N-6) - puente
de EVENTOS DE NEGOCIO al libro mayor canonico
(GeneralLedgerEngine, firma verificada):
finanzas ingreso/gasto, CxC factura/cobro, CxP
factura/pago, tesoreria deposito/retiro,
depreciacion mensual, provision fiscal,
budget_vs_actual contra el REAL del mayor
(trial_balance) y ledger_is_balanced (integridad
global: suma debitos == suma creditos).

Cada metodo genera un asiento BALANCEADO via
post_balanced (el cuadre es ley) con source_ref
"N2:<tipo>:<id>". Montos Decimal 2d (regla 61).
Catalogo de cuentas sobreescribible. Los
engines duenos de cada dominio siguen mandando
(regla 69)."""
from __future__ import annotations
from decimal import Decimal
from typing import List, Optional
from shared_engines.common.clocks import Clock
from shared_engines.storage.database import (
    Database)

_Q = Decimal("0.01")

class LedgerIntegrationEngine:
    """Integraciones de negocio al mayor."""

    def __init__(self, db, clock, ledger):
        self._db = db
        self._clock = clock
        self._gl = ledger

    @staticmethod
    def _amt(amount) -> Decimal:
        d = Decimal(str(amount)).quantize(_Q)
        if d <= Decimal("0.00"):
            raise ValueError(
                "amount debe ser > 0: "
                + str(d))
        return d

    def _post(self, company_id, period, kind,
              ref, lines) -> dict:
        res = self._gl.post_balanced(
            company_id=str(company_id),
            period=str(period),
            lines=lines,
            source_ref=("N2:" + str(kind)
                        + ":" + str(ref)))
        return {"kind": str(kind),
                "ref": str(ref),
                "posted": res["posted"],
                "total_debit":
                    res["total_debit"],
                "total_credit":
                    res["total_credit"],
                "entries": res["entries"]}

    def income_recorded(self, *, company_id,
                        period, record_id,
                        amount,
                        cash_account="1000",
                        income_account="4000"
                        ) -> dict:
        a = self._amt(amount)
        return self._post(
            company_id, period, "INGRESO",
            record_id,
            [{"account_code":
                  str(cash_account),
              "debit": str(a),
              "credit": "0"},
             {"account_code":
                  str(income_account),
              "debit": "0",
              "credit": str(a)}])

    def expense_recorded(self, *, company_id,
                         period, record_id,
                         amount,
                         expense_account="5000",
                         cash_account="1000"
                         ) -> dict:
        a = self._amt(amount)
        return self._post(
            company_id, period, "GASTO",
            record_id,
            [{"account_code":
                  str(expense_account),
              "debit": str(a),
              "credit": "0"},
             {"account_code":
                  str(cash_account),
              "debit": "0",
              "credit": str(a)}])

    def invoice_issued_ar(self, *, company_id,
                          period, invoice_id,
                          amount,
                          ar_account="1100",
                          income_account="4000"
                          ) -> dict:
        a = self._amt(amount)
        return self._post(
            company_id, period, "CXC_FACTURA",
            invoice_id,
            [{"account_code":
                  str(ar_account),
              "debit": str(a),
              "credit": "0"},
             {"account_code":
                  str(income_account),
              "debit": "0",
              "credit": str(a)}])

    def payment_received(self, *, company_id,
                         period, invoice_id,
                         amount,
                         bank_account="1000",
                         ar_account="1100"
                         ) -> dict:
        a = self._amt(amount)
        return self._post(
            company_id, period, "CXC_COBRO",
            invoice_id,
            [{"account_code":
                  str(bank_account),
              "debit": str(a),
              "credit": "0"},
             {"account_code":
                  str(ar_account),
              "debit": "0",
              "credit": str(a)}])

    def invoice_received_ap(self, *,
                            company_id, period,
                            invoice_id, amount,
                            expense_account="5000",
                            ap_account="2100"
                            ) -> dict:
        a = self._amt(amount)
        return self._post(
            company_id, period, "CXP_FACTURA",
            invoice_id,
            [{"account_code":
                  str(expense_account),
              "debit": str(a),
              "credit": "0"},
             {"account_code":
                  str(ap_account),
              "debit": "0",
              "credit": str(a)}])

    def payment_sent(self, *, company_id,
                     period, invoice_id,
                     amount,
                     ap_account="2100",
                     bank_account="1000"
                     ) -> dict:
        a = self._amt(amount)
        return self._post(
            company_id, period, "CXP_PAGO",
            invoice_id,
            [{"account_code":
                  str(ap_account),
              "debit": str(a),
              "credit": "0"},
             {"account_code":
                  str(bank_account),
              "debit": "0",
              "credit": str(a)}])

    def treasury_move(self, *, company_id,
                      period, move_id, direction,
                      amount,
                      bank_account="1000",
                      counter_account="3000"
                      ) -> dict:
        a = self._amt(amount)
        d = str(direction).upper()
        if d not in ("DEPOSIT", "WITHDRAW"):
            raise ValueError(
                "direction DEPOSIT o"
                " WITHDRAW")
        if d == "DEPOSIT":
            lines = [
                {"account_code":
                     str(bank_account),
                 "debit": str(a),
                 "credit": "0"},
                {"account_code":
                     str(counter_account),
                 "debit": "0",
                 "credit": str(a)}]
        else:
            lines = [
                {"account_code":
                     str(counter_account),
                 "debit": str(a),
                 "credit": "0"},
                {"account_code":
                     str(bank_account),
                 "debit": "0",
                 "credit": str(a)}]
        return self._post(
            company_id, period,
            "TESORERIA_" + d, move_id, lines)

    def depreciation_month(self, *,
                           company_id, period,
                           asset_id, amount,
                           expense_account="5200",
                           acc_dep_account="1590"
                           ) -> dict:
        a = self._amt(amount)
        return self._post(
            company_id, period,
            "DEPRECIACION", asset_id,
            [{"account_code":
                  str(expense_account),
              "debit": str(a),
              "credit": "0"},
             {"account_code":
                  str(acc_dep_account),
              "debit": "0",
              "credit": str(a)}])

    def tax_provision(self, *, company_id,
                      period, obligation_id,
                      amount,
                      expense_account="5300",
                      liability_account="2300"
                      ) -> dict:
        a = self._amt(amount)
        return self._post(
            company_id, period,
            "PROVISION_FISCAL",
            obligation_id,
            [{"account_code":
                  str(expense_account),
              "debit": str(a),
              "credit": "0"},
             {"account_code":
                  str(liability_account),
              "debit": "0",
              "credit": str(a)}])

    def budget_vs_actual(self, *,
                         company_id, period,
                         budgets) -> List[dict]:
        """budgets: {cuenta: monto}. El REAL
        sale del mayor (trial_balance)."""
        real = {r["account_code"]:
                Decimal(r["debit"])
                - Decimal(r["credit"])
                for r in
                self._gl.trial_balance(
                    company_id, str(period))}
        rows = []
        for acc in sorted(budgets):
            b = Decimal(
                str(budgets[acc])).quantize(_Q)
            a = real.get(str(acc),
                         Decimal("0.00"))
            diff = (a - b).quantize(_Q)
            pct = (str(
                (Decimal(a) * Decimal(100)
                 / b).quantize(_Q))
                if b != Decimal("0.00")
                else None)
            rows.append({
                "account_code": str(acc),
                "budget": str(b),
                "actual": str(a.quantize(_Q)),
                "diff": str(diff),
                "usage_pct": pct,
                "over": a > b})
        return rows

    def ledger_is_balanced(self, *,
                           company_id,
                           period=""
                           ) -> bool:
        rows = self._gl.trial_balance(
            company_id, str(period or ""))
        td = sum((Decimal(r["debit"])
                  for r in rows),
                 Decimal("0"))
        tc = sum((Decimal(r["credit"])
                  for r in rows),
                 Decimal("0"))
        return td == tc
