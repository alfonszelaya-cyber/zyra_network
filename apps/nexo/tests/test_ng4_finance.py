import pytest
from shared_engines.common.clocks import FrozenClock
from shared_engines.storage.database import SQLiteAdapter
from apps.nexo.domain.finance.accounts_receivable_engine import AccountsReceivableEngine
from apps.nexo.domain.finance.accounts_payable_engine import AccountsPayableEngine
from apps.nexo.domain.finance.treasury_engine import TreasuryEngine
from apps.nexo.domain.finance.fixed_assets_engine import FixedAssetsEngine
from apps.nexo.domain.finance.budget_engine import BudgetEngine

def test_ar_aging(tmp_path) -> None:
    db = SQLiteAdapter(tmp_path / "ar.db")
    ar = AccountsReceivableEngine(db, FrozenClock())
    inv = ar.create_invoice(company_id="EMP-AR",
        client_id="CLI-1",
        invoice_number="F-2001", amount="1000",
        credit_days=30)
    assert inv["balance"] == "1000"
    p = ar.register_payment(invoice_id=inv["invoice_id"],
        amount="400", reference="AB-1")
    assert p["balance"] == "600"
    assert p["status"] == "PARTIAL"
    with pytest.raises(ValueError):
        ar.register_payment(
            invoice_id=inv["invoice_id"],
            amount="99999")
    ag = ar.aging("EMP-AR")
    assert ag["aging"]["current"] == "600"
    assert ag["overdue_invoices"] == 0
    print("OK CxC: abonos parciales + aging + proteccion")

def test_ap_approval_flow(tmp_path) -> None:
    db = SQLiteAdapter(tmp_path / "ap.db")
    ap = AccountsPayableEngine(db, FrozenClock())
    inv = ap.create_invoice(company_id="EMP-AP",
        supplier_id="PROV-1",
        invoice_number="P-500",
        amount="800", purchase_order="OC-77")
    assert inv["status"] == "PENDING_APPROVAL"
    with pytest.raises(ValueError):
        ap.register_payment(
            invoice_id=inv["invoice_id"],
            amount="100")
    a = ap.approve_invoice(
        invoice_id=inv["invoice_id"],
        approver="gerente")
    assert a["status"] == "APPROVED"
    assert a["approved_by"] == "gerente"
    ap.register_payment(invoice_id=inv["invoice_id"],
        amount="300")
    got = ap.get_invoice(inv["invoice_id"])
    assert got["status"] == "PARTIAL"
    assert got["balance"] == "500"
    print("OK CxP: aprobacion requerida + pago parcial")

def test_treasury_position(tmp_path) -> None:
    db = SQLiteAdapter(tmp_path / "tr.db")
    tr = TreasuryEngine(db, FrozenClock())
    banco = tr.create_account(company_id="EMP-TR",
        account_name="Banco Principal",
        account_kind="BANK", bank="Banco NEXO")
    caja = tr.create_account(company_id="EMP-TR",
        account_name="Caja General",
        account_kind="CASH")
    d = tr.deposit(account_id=banco["account_id"],
        amount="5000", reference="apertura")
    assert d["balance"] == "5000.00"
    t = tr.transfer(
        from_account=banco["account_id"],
        to_account=caja["account_id"],
        amount="1200")
    assert t["from_balance"] == "3800.00"
    assert t["to_balance"] == "1200.00"
    with pytest.raises(ValueError):
        tr.withdraw(account_id=banco["account_id"],
            amount="999999")
    pos = tr.position("EMP-TR")
    assert len(pos) == 2
    tx = tr.transactions_of("EMP-TR")
    assert len(tx) == 3
    print("OK tesoreria: saldo 2d + transferencia + sin sobregiro")

def test_fixed_assets_depreciation(tmp_path) -> None:
    db = SQLiteAdapter(tmp_path / "fa.db")
    fa = FixedAssetsEngine(db, FrozenClock())
    a = fa.register_asset(company_id="EMP-FA",
        asset_name="Camion reparto",
        acquisition_cost="12000",
        useful_life_months=60,
        residual_value="2000")
    dep = fa.monthly_depreciation(a["asset_id"])
    assert dep == "166.67"
    m1 = fa.apply_month(a["asset_id"], months=12)
    assert (m1["accumulated_depreciation"]
            == "2000.04")
    assert m1["book_value"] == "9999.96"
    for _ in range(60):
        fa.apply_month(a["asset_id"])
    full = fa.get_asset(a["asset_id"])
    assert (full["accumulated_depreciation"]
            == "10000.00")
    assert full["book_value"] == "2000.00"
    d = fa.dispose(asset_id=a["asset_id"],
        reason="venta")
    assert d["status"] == "DISPOSED"
    print("OK activos: depreciacion con tope 2d + baja")

def test_budget_alerts(tmp_path) -> None:
    db = SQLiteAdapter(tmp_path / "bg.db")
    bud = BudgetEngine(db, FrozenClock())
    bud.set_budget(company_id="EMP-BG",
        period="2026-03", category="COMBUSTIBLE",
        budgeted="500")
    bud.register_actual(company_id="EMP-BG",
        period="2026-03", category="COMBUSTIBLE",
        amount="300")
    b = bud.get_budget("EMP-BG", "2026-03",
                       "COMBUSTIBLE")
    assert b["over_budget"] is False
    bud.register_actual(company_id="EMP-BG",
        period="2026-03", category="COMBUSTIBLE",
        amount="250")
    b2 = bud.get_budget("EMP-BG", "2026-03",
                        "COMBUSTIBLE")
    assert b2["over_budget"] is True
    assert b2["actual"] == "550.00"
    al = bud.alerts("EMP-BG", "2026-03")
    assert len(al) == 1
    assert al[0]["category"] == "COMBUSTIBLE"
    print("OK presupuesto: acumulado normalizado 2d + alerta")
