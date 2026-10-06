import pytest
from shared_engines.common.clocks import FrozenClock
from shared_engines.storage.database import SQLiteAdapter
from apps.nexo.domain.finance.fiscal_engine import FiscalEngine
from apps.nexo.domain.finance.fiscal_calendar_engine import FiscalCalendarEngine
from apps.nexo.domain.finance.fiscal_reconciliation_engine import FiscalReconciliationEngine

def test_fiscal_rates_and_calc(tmp_path) -> None:
    db = SQLiteAdapter(tmp_path / "fi.db")
    f = FiscalEngine(db, FrozenClock())
    f.set_rate(country="SV", tax_type="IVA",
               rate_pct="13.00")
    assert f.get_rate("SV", "IVA") == "13.00"
    assert f.calculate_tax(base="1000",
        tax_type="IVA") == "130.00"
    assert f.calculate_tax(base="1000.50",
        tax_type="IVA") == "130.07"
    with pytest.raises(ValueError):
        f.calculate_tax(base="100",
                        tax_type="NOEXISTE")
    f.set_rate(country="SV", tax_type="MUNICIPAL",
               rate_pct="5.00")
    assert f.calculate_tax(base="200",
        tax_type="MUNICIPAL") == "10.00"
    print("OK fiscal: tasas por pais + redondeo comercial HALF_UP")

def test_fiscal_obligations(tmp_path) -> None:
    db = SQLiteAdapter(tmp_path / "fo.db")
    f = FiscalEngine(db, FrozenClock())
    f.set_rate(country="SV", tax_type="IVA",
               rate_pct="13.00")
    o = f.declare_obligation(company_id="EMP-1",
        period="2026-03", tax_type="IVA",
        base="1000")
    assert o["tax_amount"] == "130.00"
    assert o["status"] == "PENDING"
    f.register_payment(obligation_id=o["obligation_id"],
        amount="50")
    o2 = f.get_obligation(o["obligation_id"])
    assert o2["paid"] == "50.00"
    assert o2["status"] == "PARTIAL"
    f.register_payment(obligation_id=o["obligation_id"],
        amount="80")
    o3 = f.get_obligation(o["obligation_id"])
    assert o3["status"] == "PAID"
    assert o3["balance"] == "0.00"
    with pytest.raises(ValueError):
        f.register_payment(
            obligation_id=o["obligation_id"],
            amount="10")
    s = f.summary("EMP-1", "2026-03")
    assert s["declared"] == "130.00"
    assert s["paid"] == "130.00"
    assert s["pending"] == "0.00"
    print("OK obligaciones: declarar->pagar->PAID + resumen")

def test_fiscal_calendar(tmp_path) -> None:
    db = SQLiteAdapter(tmp_path / "fc.db")
    cal = FiscalCalendarEngine(db, FrozenClock())
    d1 = cal.add_deadline(company_id="EMP-1",
        period="2026-03", tax_type="IVA",
        due_days=15, description="IVA marzo")
    d2 = cal.add_deadline(company_id="EMP-1",
        period="2026-02", tax_type="RENTA",
        due_days=-5, description="renta atrasada")
    up = cal.upcoming("EMP-1", days=30)
    assert len(up) == 1
    assert up[0]["tax_type"] == "IVA"
    od = cal.overdue("EMP-1")
    assert len(od) == 1
    assert od[0]["tax_type"] == "RENTA"
    cal.mark_filed(d1["deadline_id"])
    assert len(cal.upcoming("EMP-1", days=30)) == 0
    print("OK calendario: proximos + vencidos + presentado")

def test_fiscal_reconciliation(tmp_path) -> None:
    db = SQLiteAdapter(tmp_path / "fr.db")
    rec = FiscalReconciliationEngine(db, FrozenClock())
    r = rec.reconcile(company_id="EMP-1",
        period="2026-03",
        fiscal_by_type={"IVA": "130.00",
                        "RENTA": "95.00"},
        book_by_type={"IVA": "130.00",
                      "RENTA": "100.00"})
    assert r["matched"] == 1
    assert r["all_matched"] is False
    items = {i["tax_type"]: i
             for i in r["items"]}
    assert items["IVA"]["matched"] is True
    assert items["RENTA"]["difference"] == "-5.00"
    print("OK conciliacion fiscal: match + diferencia reportada")
