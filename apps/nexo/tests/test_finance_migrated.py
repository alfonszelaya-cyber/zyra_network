import pytest
from decimal import Decimal
from shared_engines.common.clocks import FrozenClock
from shared_engines.audit.chain import AuditTrail
from shared_engines.storage.database import SQLiteAdapter
from apps.nexo.domain.finance.Zyra_finance_master import ZyraFinanceMaster
from apps.nexo.domain.finance.finanzas_total import FinanzasTotal
from apps.nexo.domain.finance.tax_declarations import TaxDeclarationsEngine
from apps.nexo.application.accounting_use_cases.create_journal_entry_use_case import CreateJournalEntryUseCase


def _db(tmp_path):
    return SQLiteAdapter(tmp_path / "fin.db")


def test_finance_master_pnl(tmp_path) -> None:
    db = _db(tmp_path)
    clock = FrozenClock()
    master = ZyraFinanceMaster(db, clock, audit=AuditTrail(db, clock))
    master.accounting_engine.create_entry(account_code="4001", amount="1000.00", entry_type="CREDIT", description="venta")
    master.accounting_engine.create_entry(account_code="5001", amount="400.00", entry_type="DEBIT", description="costo")
    r = master.generar_reporte_maestro()
    assert Decimal(r["revenue"]) == Decimal("1000.00")
    assert Decimal(r["profit"]) == Decimal("600.00")
    print("OK: finance master PNL")


def test_finanzas_total(tmp_path) -> None:
    db = _db(tmp_path)
    clock = FrozenClock()
    ft = FinanzasTotal(db, clock, audit=AuditTrail(db, clock))
    ft.accounting_engine.create_entry(account_code="4001", amount="500.00", entry_type="CREDIT", description="v")
    ft.accounting_engine.create_entry(account_code="5001", amount="300.00", entry_type="DEBIT", description="e")
    r = ft.generar_reporte_maestro()
    assert Decimal(r["metricas"]["ganancia_neta"]) == Decimal("200.00")
    print("OK: finanzas_total ganancia 200")


def test_tax_declarations(tmp_path) -> None:
    db = _db(tmp_path)
    clock = FrozenClock()
    tax = TaxDeclarationsEngine(db, clock, audit=AuditTrail(db, clock))
    tax.accounting_engine.create_entry(account_code="4001", amount="2000.00", entry_type="CREDIT", description="venta")
    tax.accounting_engine.create_entry(account_code="5001", amount="800.00", entry_type="DEBIT", description="gasto")
    acc = tax.calcular_acumulados()
    assert Decimal(acc["utilidad"]) == Decimal("1200.00")
    print("OK: fiscal acumulados")


def test_use_case_journal_entry(tmp_path) -> None:
    db = _db(tmp_path)
    clock = FrozenClock()
    master = ZyraFinanceMaster(db, clock, audit=AuditTrail(db, clock))
    uc = CreateJournalEntryUseCase(master.accounting_engine, master.journal_engine)
    r = uc.execute(company_id="C1", debit_account="1101", credit_account="4001", amount="250.00", description="venta", created_by="contador")
    assert Decimal(r["amount"]) == Decimal("250.00")
    print("OK: use case partida doble")
