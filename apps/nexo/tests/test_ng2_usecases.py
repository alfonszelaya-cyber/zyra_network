import pytest
from shared_engines.common.clocks import FrozenClock
from shared_engines.storage.database import SQLiteAdapter
from apps.nexo.domain.operations.operations_engine import OperationsEngine
from apps.nexo.domain.operations.operational_control_engine import OperationalControlEngine
from apps.nexo.domain.operations.operations_validation_engine import OperationsValidationEngine
from apps.nexo.domain.operations.operational_metrics_engine import OperationalMetricsEngine
from apps.nexo.domain.operations.process_tracking_engine import ProcessTrackingEngine
from apps.nexo.application.operations_use_cases.execute_operation_use_case import ExecuteOperationUseCase
from apps.nexo.application.operations_use_cases.validate_operation_use_case import ValidateOperationUseCase
from apps.nexo.application.operations_use_cases.monitor_operation_use_case import MonitorOperationUseCase
from apps.nexo.application.operations_use_cases.generate_operation_report_use_case import GenerateOperationReportUseCase
from apps.nexo.application.operations_use_cases.generate_operational_metrics_use_case import GenerateOperationalMetricsUseCase
from apps.nexo.application.operations_use_cases.track_process_use_case import TrackProcessUseCase
from apps.nexo.application.operations_use_cases.register_logistics_cost_use_case import RegisterLogisticsCostUseCase

def test_execute_operation_usecase(tmp_path) -> None:
    db = SQLiteAdapter(tmp_path / "ex.db")
    clock = FrozenClock()
    ops = OperationsEngine(db, clock)
    val = OperationsValidationEngine(db, clock)
    track = ProcessTrackingEngine(db, clock)
    op = ops.create_operation(company_id="ALC-01",
        operation_type="PAYMENT",
        description="Pago nomina", amount="2500.00")
    oid = op["operation_id"]
    ops.transition(operation_id=oid, new_status="PENDING",
        actor="u1")
    uc = ExecuteOperationUseCase(ops, val, track)
    r = uc.execute(operation_id=oid, amount="2500.00",
        description="Pago nomina", actor="tesorero")
    assert r["executed"] is True
    assert r["status"] == "COMPLETED"
    assert r["operation_number"] == 1
    m = MonitorOperationUseCase(ops, track,
        OperationalControlEngine(db, clock)).execute(
        operation_id=oid)
    assert m["found"] is True
    assert m["all_controls_passed"] is True
    assert len(m["timeline"]) >= 1
    print("OK execute+monitor: ejecucion completa trazada")

def test_execute_rechaza_por_validacion(tmp_path) -> None:
    db = SQLiteAdapter(tmp_path / "rej.db")
    clock = FrozenClock()
    ops = OperationsEngine(db, clock)
    val = OperationsValidationEngine(db, clock)
    track = ProcessTrackingEngine(db, clock)
    op = ops.create_operation(company_id="EMP-R",
        operation_type="TRANSACTION",
        description="monto negativo", amount="100")
    oid = op["operation_id"]
    ops.transition(operation_id=oid, new_status="PENDING",
        actor="u1")
    uc = ExecuteOperationUseCase(ops, val, track)
    r = uc.execute(operation_id=oid, amount="-50",
        description="x", actor="u2")
    assert r["executed"] is False
    got = ops.get_operation(oid)
    assert got["status"] == "REJECTED"
    print("OK execute: rechazo con validacion fallida")

def test_validate_operation_usecase(tmp_path) -> None:
    db = SQLiteAdapter(tmp_path / "vv.db")
    clock = FrozenClock()
    val = OperationsValidationEngine(db, clock)
    ctrl = OperationalControlEngine(db, clock)
    uc = ValidateOperationUseCase(val, ctrl)
    r = uc.execute(operation_id="OP-W1", amount="500",
        description="pago ok", amount_limit="1000",
        fingerprint="F1", previous_fingerprints=[])
    assert r["valid"] is True
    r2 = uc.execute(operation_id="OP-W2", amount="5000",
        description="monto grande",
        amount_limit="1000", fingerprint="F2",
        previous_fingerprints=[])
    assert r2["valid"] is False
    assert r2["amount_limit"]["passed"] is False
    r3 = uc.execute(operation_id="OP-W3", amount="100",
        description="duplicado", amount_limit="1000",
        fingerprint="F1",
        previous_fingerprints=["F1"])
    assert r3["valid"] is False
    assert r3["duplicate_check"]["duplicate"] is True
    print("OK validate use case: limite + duplicado")

def test_report_and_track_usecase(tmp_path) -> None:
    db = SQLiteAdapter(tmp_path / "rp.db")
    clock = FrozenClock()
    ops = OperationsEngine(db, clock)
    track = ProcessTrackingEngine(db, clock)
    op = ops.create_operation(company_id="EMP-RP",
        operation_type="DECLARATION",
        description="IVA marzo", amount="320.00")
    oid = op["operation_id"]
    track.append_event(process_id=oid,
        event_type="NOTE", actor="contador",
        detail="preparada")
    rep = GenerateOperationReportUseCase(
        ops, track).execute(operation_id=oid)
    assert rep["report_type"] == "OPERATION_REPORT"
    assert rep["operation"]["operation_id"] == oid
    assert rep["company_totals"]["total_operations"] == 1
    t = TrackProcessUseCase(track).execute(
        process_id=oid, event_type="SENT",
        actor="sistema", detail="enviada")
    assert t["total_events"] == 2
    print("OK report+track: reporte formal con timeline")

def test_metrics_usecase(tmp_path) -> None:
    db = SQLiteAdapter(tmp_path / "mu.db")
    clock = FrozenClock()
    ops = OperationsEngine(db, clock)
    metrics = OperationalMetricsEngine(db, clock)
    op = ops.create_operation(company_id="EMP-M",
        operation_type="PAYMENT",
        description="pago", amount="100.00")
    for st in ("PENDING", "VALIDATED", "APPROVED",
               "IN_PROGRESS", "COMPLETED"):
        ops.transition(operation_id=op["operation_id"],
            new_status=st, actor="u")
    r = GenerateOperationalMetricsUseCase(
        metrics).execute(company_id="EMP-M",
        period="2026-04")
    assert r["metrics"]["total_operations"] == "1"
    assert r["metrics"]["active_amount"] == "100.00"
    assert len(r["stored"]) == 4
    print("OK metrics use case: calculadas y persistidas")

def test_logistics_cost_usecase(tmp_path) -> None:
    db = SQLiteAdapter(tmp_path / "lcuc.db")
    ops = OperationsEngine(db, FrozenClock())
    uc = RegisterLogisticsCostUseCase(ops)
    r = uc.execute(company_id="EMP-LC2",
        description="Flete entrega F-200",
        amount="45.25", reference="F-200",
        carrier="Transportes XYZ")
    assert r["amount"] == "45.25"
    assert r["operation_type"] == "LOGISTICS_COST"
    assert r["status"] == "DRAFT"
    ls = ops.list_by_company("EMP-LC2")
    assert ls[0]["operation_type"] == "LOGISTICS_COST"
    print("OK costo logistico: contable en libros (regla 70)")
