import pytest
from shared_engines.common.clocks import FrozenClock
from shared_engines.storage.database import SQLiteAdapter
from apps.nexo.domain.finance.finance_engine import FinanceEngine
from apps.nexo.domain.finance.finance_registry import FinanceRegistry
from apps.nexo.domain.finance.financial_validation_engine import FinancialValidationEngine
from apps.nexo.domain.finance.treasury_engine import TreasuryEngine
from apps.nexo.domain.finance.budget_engine import BudgetEngine
from apps.nexo.application.finance_use_cases.create_financial_record_use_case import CreateFinancialRecordUseCase
from apps.nexo.application.finance_use_cases.generate_financial_report_use_case import GenerateFinancialReportUseCase
from apps.nexo.application.finance_use_cases.process_financial_operation_use_case import ProcessFinancialOperationUseCase
from apps.nexo.application.finance_use_cases.validate_financial_operation_use_case import ValidateFinancialOperationUseCase

def _setup(tmp_path):
    db = SQLiteAdapter(tmp_path / "fin.db")
    clock = FrozenClock()
    val = FinancialValidationEngine(db, clock)
    eng = FinanceEngine(db, clock)
    reg = FinanceRegistry(db, clock)
    trs = TreasuryEngine(db, clock)
    bud = BudgetEngine(db, clock)
    return db, clock, val, eng, reg, trs, bud

def test_validate_usecase(tmp_path) -> None:
    _, _, val, _, _, _, _ = _setup(tmp_path)
    uc = ValidateFinancialOperationUseCase(val)
    r = uc.execute(amount="100", currency="USD",
                   category="VENTAS",
                   period="2026-03")
    assert r["valid"] is True
    r2 = uc.execute(amount="-5", currency="XXX",
                    category="", period="")
    assert r2["valid"] is False
    print("OK validate fin: reglas de produccion")

def test_create_record_usecase(tmp_path) -> None:
    _, _, val, eng, reg, _, _ = _setup(tmp_path)
    uc = CreateFinancialRecordUseCase(val, eng, reg)
    r = uc.execute(company_id="EMP-F",
        period="2026-03", record_type="INCOME",
        amount="1500", category="VENTAS",
        actor="contador")
    assert r["created"] is True
    evs = reg.events_of("EMP-F")
    assert evs[0]["event_type"] == "RECORD_CREATED"
    r2 = uc.execute(company_id="EMP-F",
        period="2026-03", record_type="INCOME",
        amount="0", category="VENTAS")
    assert r2["created"] is False
    print("OK create record: crea + traza + rechaza")

def test_process_operation_usecase(tmp_path) -> None:
    _, _, val, eng, reg, trs, bud = _setup(tmp_path)
    banco = trs.create_account(
        company_id="EMP-PO",
        account_name="Banco", account_kind="BANK")
    bud.set_budget(company_id="EMP-PO",
        period="2026-03", category="LOGISTICA",
        budgeted="1000")
    uc = ProcessFinancialOperationUseCase(
        val, eng, treasury=trs, budget=bud)
    r1 = uc.execute(company_id="EMP-PO",
        period="2026-03", record_type="INCOME",
        amount="3000", category="VENTAS",
        treasury_account=banco["account_id"],
        reference="cobro F-1")
    assert r1["processed"] is True
    assert (r1["treasury_tx"]["balance"]
            == "3000.00")
    r2 = uc.execute(company_id="EMP-PO",
        period="2026-03", record_type="EXPENSE",
        amount="600", category="LOGISTICA",
        treasury_account=banco["account_id"],
        reference="flete")
    assert r2["processed"] is True
    assert r2["budget"]["over_budget"] is False
    acc = trs.get_account(banco["account_id"])
    assert acc["balance"] == "2400.00"
    print("OK proceso fin: valida+registra+tesoreria 2d+presupuesto")

def test_financial_report_usecase(tmp_path) -> None:
    _, _, val, eng, reg, trs, bud = _setup(tmp_path)
    eng.create_record(company_id="EMP-R",
        period="2026-03", record_type="INCOME",
        amount="2000", category="VENTAS")
    eng.create_record(company_id="EMP-R",
        period="2026-03", record_type="EXPENSE",
        amount="700", category="LOGISTICA")
    bud.set_budget(company_id="EMP-R",
        period="2026-03", category="LOGISTICA",
        budgeted="500")
    r = GenerateFinancialReportUseCase(
        eng, bud).execute(company_id="EMP-R",
        period="2026-03")
    assert r["totals"]["income"] == "2000"
    assert r["totals"]["expense"] == "700"
    assert r["totals"]["net"] == "1300"
    assert len(r["budget_alerts"]) == 0
    print("OK reporte fin: totales + presupuestos del periodo")
