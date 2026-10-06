import pytest
from shared_engines.common.clocks import FrozenClock
from shared_engines.storage.database import SQLiteAdapter
from apps.nexo.domain.accounting.chart_of_accounts_engine import ChartOfAccountsEngine
from apps.nexo.domain.accounting.general_ledger_engine import GeneralLedgerEngine
from apps.nexo.domain.accounting.financial_statements_engine import FinancialStatementsEngine
from apps.nexo.domain.accounting.period_closing_engine import PeriodClosingEngine
from apps.nexo.domain.accounting.recurring_entries_engine import RecurringEntriesEngine
from apps.nexo.domain.accounting.cost_center_engine import CostCenterEngine

def _setup(tmp_path):
    db = SQLiteAdapter(tmp_path / "ac.db")
    clock = FrozenClock()
    chart = ChartOfAccountsEngine(db, clock)
    chart.install_template(company_id="EMP-AC")
    ledger = GeneralLedgerEngine(db, clock)
    return db, clock, chart, ledger

def test_chart_of_accounts(tmp_path) -> None:
    db, clock, chart, ledger = _setup(tmp_path)
    accs = chart.accounts_of("EMP-AC")
    assert len(accs) == 12
    efectivo = chart.get_account("EMP-AC", "1000")
    assert efectivo["account_type"] == "ASSET"
    with pytest.raises(ValueError):
        chart.add_account(company_id="EMP-AC",
            account_code="9999",
            account_name="mal",
            account_type="INVALIDO")
    print("OK chart: 12 cuentas plantilla + tipo invalido")

def test_general_ledger_balanced(tmp_path) -> None:
    db, clock, chart, ledger = _setup(tmp_path)
    r = ledger.post_balanced(company_id="EMP-AC",
        period="2026-03", source_ref="F-1001",
        lines=[
            {"account_code": "1000",
             "debit": "500", "credit": "0"},
            {"account_code": "4000",
             "debit": "0", "credit": "500"}])
    assert r["posted"] == 2
    bal = ledger.account_balance("EMP-AC", "1000",
                                 "2026-03")
    assert bal["balance"] == "500.00"
    assert bal["debit"] == "500.00"
    with pytest.raises(ValueError):
        ledger.post_balanced(company_id="EMP-AC",
            period="2026-03",
            lines=[
                {"account_code": "1000",
                 "debit": "100", "credit": "0"},
                {"account_code": "4000",
                 "debit": "0", "credit": "90"}])
    tb = ledger.trial_balance("EMP-AC", "2026-03")
    assert len(tb) == 2
    assert tb[0]["debit"] == "500.00"
    print("OK mayor: asiento cuadrado + Decimal 2d + rechazo descuadre")

def test_financial_statements(tmp_path) -> None:
    db, clock, chart, ledger = _setup(tmp_path)
    ledger.post_balanced(company_id="EMP-AC",
        period="2026-03", lines=[
            {"account_code": "1000",
             "debit": "1000", "credit": "0"},
            {"account_code": "4000",
             "debit": "0", "credit": "1000"}])
    ledger.post_balanced(company_id="EMP-AC",
        period="2026-03", lines=[
            {"account_code": "6000",
             "debit": "300", "credit": "0"},
            {"account_code": "1000",
             "debit": "0", "credit": "300"}])
    st = FinancialStatementsEngine(db, clock,
        chart=chart, ledger=ledger)
    isr = st.income_statement("EMP-AC", "2026-03")
    assert isr["ingresos"] == "1000.00"
    assert isr["gastos"] == "300.00"
    assert isr["utilidad"] == "700.00"
    bs = st.balance_sheet("EMP-AC", "2026-03")
    assert bs["activos"] == "700.00"
    assert bs["pasivos"] == "0.00"
    assert bs["patrimonio"] == "700.00"
    assert bs["cuadra"] is True
    print("OK estados: resultados 700.00 + balance cuadrado bool")

def test_period_closing(tmp_path) -> None:
    db = SQLiteAdapter(tmp_path / "pc.db")
    clock = FrozenClock()
    chart = ChartOfAccountsEngine(db, clock)
    chart.install_template(company_id="EMP-AC")
    periods = PeriodClosingEngine(db, clock)
    ledger = GeneralLedgerEngine(db, clock,
        period_engine=periods)
    periods.ensure_open("EMP-AC", "2026-03")
    ledger.post_balanced(company_id="EMP-AC",
        period="2026-03", lines=[
            {"account_code": "1000",
             "debit": "1000", "credit": "0"},
            {"account_code": "4000",
             "debit": "0", "credit": "1000"}])
    closed = periods.close_period(
        company_id="EMP-AC", period="2026-03",
        actor="contador")
    assert closed["status"] == "CLOSED"
    assert closed["closed_by"] == "contador"
    with pytest.raises(ValueError):
        ledger.post_entry(company_id="EMP-AC",
            period="2026-03",
            account_code="1000", debit="1")
    with pytest.raises(ValueError):
        periods.close_period(company_id="EMP-AC",
            period="2026-03", actor="x")
    ev = periods.events_of("EMP-AC", "2026-03")
    assert any(e["event_type"] == "CLOSED"
               for e in ev)
    reop = periods.reopen_period(
        company_id="EMP-AC", period="2026-03",
        actor="auditor", reason="ajuste fiscal")
    assert reop["status"] == "OPEN"
    print("OK cierres: bloqueo real via mayor + reapertura auditada")

def test_recurring_and_cost_centers(tmp_path) -> None:
    db, clock, chart, ledger = _setup(tmp_path)
    rec = RecurringEntriesEngine(db, clock)
    t = rec.create_template(company_id="EMP-AC",
        name="Renta oficina", frequency="MONTHLY",
        lines=[
            {"account_code": "6000",
             "debit": "250", "credit": "0"},
            {"account_code": "1000",
             "debit": "0", "credit": "250"}])
    assert t["total"] == "250.00"
    r1 = rec.run_template(t["template_id"])
    assert r1["run_count"] == 1
    with pytest.raises(ValueError):
        rec.create_template(company_id="EMP-AC",
            name="mal", frequency="MONTHLY",
            lines=[
                {"account_code": "6000",
                 "debit": "10", "credit": "0"},
                {"account_code": "1000",
                 "debit": "0", "credit": "5"}])
    cc = CostCenterEngine(db, clock)
    cc.create_center(company_id="EMP-AC",
        center_code="SUC-1",
        center_name="Sucursal Centro",
        center_type="DEPARTMENT")
    ledger.post_entry(company_id="EMP-AC",
        period="2026-03", account_code="6000",
        debit="80", cost_center="SUC-1")
    ex = cc.expenses_by_center(ledger, "EMP-AC",
                               "2026-03")
    assert ex[0]["cost_center"] == "SUC-1"
    assert ex[0]["neto"] == "80.00"
    print("OK recurrentes+centros: total 2d y gasto por centro")
