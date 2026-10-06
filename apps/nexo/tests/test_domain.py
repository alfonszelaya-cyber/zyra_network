import importlib, pathlib, pytest

BASE = pathlib.Path(__file__).resolve().parents[1] / "domain"

def test_import_todos_los_engines_de_dominio():
    mods = []
    errores = []
    for p in sorted(BASE.rglob("*.py")):
        if p.stat().st_size <= 1:
            continue
        rel = ("apps.nexo."
               + p.relative_to(BASE.parent)
               .as_posix()[:-3].replace("/", "."))
        try:
            importlib.import_module(rel)
            mods.append(rel)
        except Exception as e:
            errores.append(rel + ": " + str(e)[:80])
    assert errores == []
    assert len(mods) >= 80
    print("OK domain: " + str(len(mods))
          + " modulos importan sin errores")

def test_e2e_flujo_contable_completo(tmp_path):
    from shared_engines.common.clocks import FrozenClock
    from shared_engines.storage.database import SQLiteAdapter
    from apps.nexo.domain.accounting.chart_of_accounts_engine import ChartOfAccountsEngine
    from apps.nexo.domain.accounting.general_ledger_engine import GeneralLedgerEngine
    from apps.nexo.domain.accounting.financial_statements_engine import FinancialStatementsEngine
    from apps.nexo.domain.accounting.period_closing_engine import PeriodClosingEngine
    from apps.nexo.application.accounting_use_cases.close_accounting_period_use_case import CloseAccountingPeriodUseCase
    db = SQLiteAdapter(tmp_path / "e2e.db")
    clock = FrozenClock()
    chart = ChartOfAccountsEngine(db, clock)
    chart.install_template(company_id="EMP-E2E")
    periods = PeriodClosingEngine(db, clock)
    periods.ensure_open("EMP-E2E", "2026-03")
    ledger = GeneralLedgerEngine(db, clock,
        period_engine=periods)
    ledger.post_balanced(company_id="EMP-E2E",
        period="2026-03", lines=[
            {"account_code": "1000",
             "debit": "1000", "credit": "0"},
            {"account_code": "4000",
             "debit": "0", "credit": "1000"}])
    ledger.post_balanced(company_id="EMP-E2E",
        period="2026-03", lines=[
            {"account_code": "6000",
             "debit": "300", "credit": "0"},
            {"account_code": "1000",
             "debit": "0", "credit": "300"}])
    st = FinancialStatementsEngine(db, clock,
        chart=chart, ledger=ledger)
    assert (st.income_statement("EMP-E2E", "2026-03")
            ["utilidad"] == "700.00")
    r = CloseAccountingPeriodUseCase(
        periods, st, ledger).execute(
        company_id="EMP-E2E", period="2026-03",
        actor="contador")
    assert r["status"] == "CLOSED"
    assert r["utilidad"] == "700.00"
    with pytest.raises(ValueError):
        ledger.post_entry(company_id="EMP-E2E",
            period="2026-03", account_code="1000",
            debit="1")
    print("OK E2E contable: plantilla->asientos->estados->cierre->bloqueo")
