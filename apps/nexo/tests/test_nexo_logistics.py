from shared_engines.common.clocks import FrozenClock
from shared_engines.storage.database import SQLiteAdapter
from apps.nexo.domain.operations.operations_engine import OperationsEngine
from apps.nexo.application.operations_use_cases.register_logistics_cost_use_case import RegisterLogisticsCostUseCase

def test_logistica_solo_contable(tmp_path):
    ops = OperationsEngine(
        SQLiteAdapter(tmp_path / "lc.db"), FrozenClock())
    uc = RegisterLogisticsCostUseCase(ops)
    r = uc.execute(company_id="EMP-L",
        description="Flete F-1", amount="45.50",
        reference="F-1", carrier="Transportes X")
    assert r["operation_type"] == "LOGISTICS_COST"
    assert r["amount"] == "45.50"
    assert (ops.list_by_company("EMP-L")[0]
            ["operation_type"] == "LOGISTICS_COST")
    print("OK logistica NEXO: solo costo contable (regla 70)")
