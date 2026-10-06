import pytest
from shared_engines.common.clocks import FrozenClock
from shared_engines.storage.database import SQLiteAdapter
from apps.nexo.domain.accounting.chart_of_accounts_engine import ChartOfAccountsEngine
from apps.nexo.domain.accounting.general_ledger_engine import GeneralLedgerEngine
from apps.nexo.domain.accounting.financial_statements_engine import FinancialStatementsEngine
from apps.nexo.domain.accounting.period_closing_engine import PeriodClosingEngine
from apps.nexo.application.accounting_use_cases.generate_balance_use_case import GenerateBalanceUseCase
from apps.nexo.application.accounting_use_cases.generate_accounting_report_use_case import GenerateAccountingReportUseCase
from apps.nexo.application.accounting_use_cases.close_accounting_period_use_case import CloseAccountingPeriodUseCase
from apps.nexo.application.accounting_use_cases.reconcile_accounts_use_case import ReconcileAccountsUseCase

def test_generate_balance_usecase(tmp_path) -> None:
    db = SQLiteAdapter(tmp_path / "gb.db")
    clock = FrozenClock()
    chart = ChartOfAccountsEngine(db, clock)
    chart.install_template(company_id="EMP-GB")
    ledger = GeneralLedgerEngine(db, clock)
    ledger.post_balanced(company_id="EMP-GB",
        period="2026-03", lines=[
            {"account_code": "1000",
             "debit": "900", "credit": "0"},
            {"account_code": "4000",
             "debit": "0", "credit": "900"}])
    st = FinancialStatementsEngine(db, clock,
        chart=chart, ledger=ledger)
    r = GenerateBalanceUseCase(ledger, chart,
                               st).execute(
        company_id="EMP-GB", period="2026-03")
    assert r["cuadrado"] is True
    assert r["total_debit"] == "900.00"
    assert r["total_credit"] == "900.00"
    assert r["balance_sheet"]["cuadra"] is True
    print("OK balance use case: cuadrado bool + 2 decimales")

def test_accounting_report_usecase(tmp_path) -> None:
    db = SQLiteAdapter(tmp_path / "gr.db")
    clock = FrozenClock()
    chart = ChartOfAccountsEngine(db, clock)
    chart.install_template(company_id="EMP-GR")
    ledger = GeneralLedgerEngine(db, clock)
    st = FinancialStatementsEngine(db, clock,
        chart=chart, ledger=ledger)
    ledger.post_balanced(company_id="EMP-GR",
        period="2026-04", lines=[
            {"account_code": "1000",
             "debit": "2000", "credit": "0"},
            {"account_code": "4000",
             "debit": "0", "credit": "2000"}])
    r = GenerateAccountingReportUseCase(st).execute(
        company_id="EMP-GR", period="2026-04")
    assert (r["income_statement"]["utilidad"]
            == "2000.00")
    assert "balance_sheet" in r
    assert "cash_flow" in r
    print("OK reporte contable: 3 estados con Decimal 2d")

def test_close_period_usecase(tmp_path) -> None:
    db = SQLiteAdapter(tmp_path / "cp.db")
    clock = FrozenClock()
    chart = ChartOfAccountsEngine(db, clock)
    chart.install_template(company_id="EMP-CP")
    ledger = GeneralLedgerEngine(db, clock)
    periods = PeriodClosingEngine(db, clock)
    periods.ensure_open("EMP-CP", "2026-03")
    st = FinancialStatementsEngine(db, clock,
        chart=chart, ledger=ledger)
    ledger.post_balanced(company_id="EMP-CP",
        period="2026-03", lines=[
            {"account_code": "1000",
             "debit": "1500", "credit": "0"},
            {"account_code": "4000",
             "debit": "0", "credit": "1500"}])
    r = CloseAccountingPeriodUseCase(
        periods, st, ledger).execute(
        company_id="EMP-CP", period="2026-03",
        actor="contador")
    assert r["status"] == "CLOSED"
    assert r["utilidad"] == "1500.00"
    assert r["closing_posted"] == 2
    p = periods.get_period("EMP-CP", "2026-03")
    assert p["status"] == "CLOSED"
    print("OK cierre use case: asiento sin lineas vacias + bloqueo")

def test_reconcile_usecase(tmp_path) -> None:
    db = SQLiteAdapter(tmp_path / "rc.db")
    clock = FrozenClock()
    ledger = GeneralLedgerEngine(db, clock)
    ledger.post_entry(company_id="EMP-RC",
        period="2026-03", account_code="1000",
        debit="500")
    r = ReconcileAccountsUseCase(ledger).execute(
        company_id="EMP-RC", period="2026-03",
        expected_balances={"1000": "500.00",
                           "2000": "0.00"})
    assert r["reconciled"] == 2
    assert r["all_matched"] is True
    r2 = ReconcileAccountsUseCase(ledger).execute(
        company_id="EMP-RC", period="2026-03",
        expected_balances={"1000": "999.00"})
    assert r2["reconciled"] == 0
    assert r2["items"][0]["matched"] is False
    print("OK conciliacion: match 2d + diferencia detectada")
