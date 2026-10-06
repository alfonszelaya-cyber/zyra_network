import importlib, pathlib
from shared_engines.common.clocks import FrozenClock
from shared_engines.storage.database import SQLiteAdapter
from apps.nexo.domain.accounting.chart_of_accounts_engine import ChartOfAccountsEngine
from apps.nexo.domain.accounting.general_ledger_engine import GeneralLedgerEngine

BASE = pathlib.Path(__file__).resolve().parents[1] / "domain" / "accounting"

def test_modulos_accounting_importan():
    n = 0
    for p in sorted(BASE.glob("*.py")):
        if p.stat().st_size <= 1:
            continue
        importlib.import_module(
            "apps.nexo.domain.accounting." + p.stem)
        n = n + 1
    assert n >= 10
    print("OK accounting: " + str(n) + " modulos importan")

def test_nucleo_contable_operates(tmp_path):
    chart = ChartOfAccountsEngine(
        SQLiteAdapter(tmp_path / "a.db"), FrozenClock())
    chart.install_template(company_id="EMP-T")
    ledger = GeneralLedgerEngine(
        SQLiteAdapter(tmp_path / "b.db"), FrozenClock())
    ledger.post_balanced(company_id="EMP-T",
        period="2026-03", lines=[
            {"account_code": "1000",
             "debit": "100", "credit": "0"},
            {"account_code": "4000",
             "debit": "0", "credit": "100"}])
    assert len(ledger.trial_balance("EMP-T",
                                    "2026-03")) == 2
    print("OK accounting: plantilla + asiento cuadrado")
