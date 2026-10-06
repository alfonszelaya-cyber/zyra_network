import importlib, pathlib
from shared_engines.common.clocks import FrozenClock
from shared_engines.storage.database import SQLiteAdapter
from apps.nexo.domain.finance.accounts_receivable_engine import AccountsReceivableEngine
from apps.nexo.domain.finance.treasury_engine import TreasuryEngine

BASE = pathlib.Path(__file__).resolve().parents[1] / "domain" / "finance"

def test_modulos_finance_importan():
    n = 0
    for p in sorted(BASE.glob("*.py")):
        if p.stat().st_size <= 1:
            continue
        importlib.import_module(
            "apps.nexo.domain.finance." + p.stem)
        n = n + 1
    assert n >= 10
    print("OK finance: " + str(n) + " modulos importan")

def test_cxc_y_tesoreria(tmp_path):
    ar = AccountsReceivableEngine(
        SQLiteAdapter(tmp_path / "ar.db"), FrozenClock())
    inv = ar.create_invoice(company_id="EMP-F",
        client_id="C1", invoice_number="F-1",
        amount="500")
    ar.register_payment(invoice_id=inv["invoice_id"],
        amount="500")
    assert (ar.get_invoice(inv["invoice_id"])["status"]
            == "PAID")
    tr = TreasuryEngine(
        SQLiteAdapter(tmp_path / "tr.db"), FrozenClock())
    acc = tr.create_account(company_id="EMP-F",
        account_name="Banco")
    tr.deposit(account_id=acc["account_id"],
               amount="1000")
    assert (tr.get_account(acc["account_id"])["balance"]
            == "1000.00")
    print("OK finance: CxC pagada + deposito 2d")
