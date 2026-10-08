import pytest
from shared_engines.common.clocks import FrozenClock
from shared_engines.storage.database import SQLiteAdapter
from apps.nexo.domain.accounting.general_ledger_engine import GeneralLedgerEngine
from apps.nexo.domain.accounting.ledger_integration_engine import LedgerIntegrationEngine


def _env(tmp_path):
    db = SQLiteAdapter(tmp_path / "n.db")
    clock = FrozenClock()
    gl = GeneralLedgerEngine(db, clock)
    itg = LedgerIntegrationEngine(db, clock, gl)
    return db, gl, itg


def test_cxc_ciclo_factura_y_cobro(tmp_path) -> None:
    db, gl, itg = _env(tmp_path)
    r1 = itg.invoice_issued_ar(company_id="EMP-1",
        period="2026-01", invoice_id="INV-1",
        amount="1000.00")
    assert r1["total_debit"] == "1000.00"
    assert r1["total_credit"] == "1000.00"
    bal_ar = gl.account_balance("EMP-1", "1100",
                                "2026-01")
    assert bal_ar["balance"] == "1000.00"
    bal_inc = gl.account_balance("EMP-1", "4000",
                                 "2026-01")
    assert bal_inc["balance"] == "-1000.00"
    r2 = itg.payment_received(company_id="EMP-1",
        period="2026-01", invoice_id="INV-1",
        amount="1000.00")
    assert r2["total_debit"] == "1000.00"
    bal_ar2 = gl.account_balance("EMP-1", "1100",
                                 "2026-01")
    assert bal_ar2["balance"] == "0.00"
    bal_bank = gl.account_balance("EMP-1", "1000",
                                  "2026-01")
    assert bal_bank["balance"] == "1000.00"
    assert itg.ledger_is_balanced(
        company_id="EMP-1") is True
    assert all(e["source_ref"].startswith("N2:")
               for e in gl.entries_of("EMP-1",
                                      "1100"))
    print("OK N-2 CxC: factura -> D CxC / C Ingreso; cobro -> D Bancos / C CxC; mayor cuadrado global + source_ref N2:*")


def test_cxp_tesoreria_activo_fiscal(tmp_path) -> None:
    db, gl, itg = _env(tmp_path)
    itg.invoice_received_ap(company_id="EMP-2",
        period="2026-02", invoice_id="INV-9",
        amount="400.00")
    itg.payment_sent(company_id="EMP-2",
        period="2026-02", invoice_id="INV-9",
        amount="400.00")
    ap = gl.account_balance("EMP-2", "2100",
                            "2026-02")
    assert ap["balance"] == "0.00"
    with pytest.raises(ValueError):
        itg.treasury_move(company_id="EMP-2",
            period="2026-02", move_id="M1",
            direction="OTRO", amount="10")
    itg.treasury_move(company_id="EMP-2",
        period="2026-02", move_id="M2",
        direction="DEPOSIT", amount="500.00")
    bank = gl.account_balance("EMP-2", "1000",
                              "2026-02")
    assert bank["balance"] == "100.00"
    itg.depreciation_month(company_id="EMP-2",
        period="2026-02", asset_id="ACT-1",
        amount="50.00")
    dep = gl.account_balance("EMP-2", "1590",
                             "2026-02")
    assert dep["balance"] == "-50.00"
    itg.tax_provision(company_id="EMP-2",
        period="2026-02", obligation_id="OBL-1",
        amount="30.00")
    with pytest.raises(ValueError):
        itg.expense_recorded(company_id="EMP-2",
            period="2026-02", record_id="X",
            amount="0")
    assert itg.ledger_is_balanced(
        company_id="EMP-2",
        period="2026-02") is True
    print("OK N-2 CxP/Tesoreria/Activos/Fiscal: pagos cancelan CxP, deposito cuadrado, depreciacion y provision; amount<=0 rechazado")


def test_presupuesto_vs_real_y_descuadre(tmp_path) -> None:
    db, gl, itg = _env(tmp_path)
    itg.expense_recorded(company_id="EMP-3",
        period="2026-03", record_id="G1",
        amount="120.00",
        expense_account="5000")
    itg.expense_recorded(company_id="EMP-3",
        period="2026-03", record_id="G2",
        amount="80.00",
        expense_account="5000")
    rows = itg.budget_vs_actual(company_id="EMP-3",
        period="2026-03",
        budgets={"5000": "150.00",
                 "6000": "10.00"})
    r5 = [r for r in rows
          if r["account_code"] == "5000"][0]
    assert r5["actual"] == "200.00"
    assert r5["over"] is True
    assert r5["usage_pct"] == "133.33"
    r6 = [r for r in rows
          if r["account_code"] == "6000"][0]
    assert r6["actual"] == "0.00"
    assert r6["over"] is False
    itg._gl._db.execute(
        "DELETE FROM nexo_gl_entries WHERE"
        " company_id = 'EMP-3' AND account_code ="
        " '1000' AND period = '2026-03'")
    assert itg.ledger_is_balanced(
        company_id="EMP-3",
        period="2026-03") is False
    print("OK N-2/N-6: budget_vs_actual contra REAL del mayor + descuadre REAL detectado al eliminar una pata del asiento")
