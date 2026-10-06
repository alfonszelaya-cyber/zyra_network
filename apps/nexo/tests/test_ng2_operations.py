import pytest
from shared_engines.common.clocks import FrozenClock
from shared_engines.storage.database import SQLiteAdapter
from apps.nexo.domain.operations.operations_engine import OperationsEngine
from apps.nexo.domain.operations.operational_control_engine import OperationalControlEngine
from apps.nexo.domain.operations.operations_validation_engine import OperationsValidationEngine
from apps.nexo.domain.operations.operational_metrics_engine import OperationalMetricsEngine
from apps.nexo.domain.operations.process_tracking_engine import ProcessTrackingEngine

def test_operation_lifecycle(tmp_path) -> None:
    db = SQLiteAdapter(tmp_path / "ops.db")
    clock = FrozenClock()
    ops = OperationsEngine(db, clock)
    op = ops.create_operation(company_id="EMP-001",
        operation_type="TRANSACTION",
        description="Cobro servicio alcaldia",
        amount="1500.50", currency="USD",
        requested_by="usuario1")
    assert op["status"] == "DRAFT"
    assert op["operation_number"] == 1
    op2 = ops.create_operation(company_id="EMP-001",
        operation_type="DECLARATION",
        description="Declaracion IVA",
        amount="320.00")
    assert op2["operation_number"] == 2
    a = ops.transition(operation_id=op["operation_id"],
        new_status="PENDING", actor="u1")
    assert a["status"] == "PENDING"
    v = ops.transition(operation_id=op["operation_id"],
        new_status="VALIDATED", actor="auditor")
    assert v["status"] == "VALIDATED"
    ap = ops.transition(operation_id=op["operation_id"],
        new_status="APPROVED", actor="gerente")
    assert ap["approved_by"] == "gerente"
    ops.transition(operation_id=op["operation_id"],
        new_status="IN_PROGRESS", actor="sys")
    c = ops.transition(operation_id=op["operation_id"],
        new_status="COMPLETED", actor="sys")
    assert c["status"] == "COMPLETED"
    assert c["completed_at"] is not None
    with pytest.raises(ValueError):
        ops.transition(operation_id=op["operation_id"],
            new_status="PENDING", actor="x")
    totals = ops.company_totals("EMP-001")
    assert totals["total_operations"] == 2
    assert totals["completed"] == 1
    assert totals["active_amount"] == "1500.50"
    for st in ("PENDING", "VALIDATED", "APPROVED",
               "IN_PROGRESS", "COMPLETED"):
        ops.transition(operation_id=op2["operation_id"],
            new_status=st, actor="u1")
    totals2 = ops.company_totals("EMP-001")
    assert totals2["completed"] == 2
    assert totals2["active_amount"] == "1820.50"
    print("OK operations: ciclo completo + filtro por estado + Decimal")

def test_logistics_cost_type(tmp_path) -> None:
    db = SQLiteAdapter(tmp_path / "lc.db")
    ops = OperationsEngine(db, FrozenClock())
    op = ops.create_operation(company_id="EMP-LC",
        operation_type="LOGISTICS_COST",
        description="Flete entrega factura F-100",
        amount="45.25",
        metadata={"reference": "F-100",
                  "carrier": "Transportes XYZ"})
    assert op["operation_type"] == "LOGISTICS_COST"
    assert op["amount"] == "45.25"
    ls = ops.list_by_company("EMP-LC")
    assert len(ls) == 1
    assert ls[0]["operation_type"] == "LOGISTICS_COST"
    print("OK operations: LOGISTICS_COST contable (regla 70)")

def test_controls_engine(tmp_path) -> None:
    db = SQLiteAdapter(tmp_path / "ctrl.db")
    ctrl = OperationalControlEngine(db, FrozenClock())
    c1 = ctrl.register_control(operation_id="OP-OK",
        control_type="AMOUNT_LIMIT")
    r1 = ctrl.check_amount_limit(
        control_id=c1["control_id"], amount="500",
        limit="1000")
    assert r1["passed"] is True
    assert ctrl.all_passed("OP-OK") is True
    c2 = ctrl.register_control(operation_id="OP-BAD",
        control_type="AMOUNT_LIMIT")
    r2 = ctrl.check_amount_limit(
        control_id=c2["control_id"], amount="5000",
        limit="1000")
    assert r2["passed"] is False
    assert ctrl.all_passed("OP-BAD") is False
    d1 = ctrl.register_control(operation_id="OP-DUP",
        control_type="DUPLICATE")
    r3 = ctrl.check_duplicate(
        control_id=d1["control_id"], fingerprint="FP-1",
        previous_fingerprints=["FP-1"])
    assert r3["duplicate"] is True
    assert r3["passed"] is False
    print("OK controls: limite Decimal + duplicado")

def test_validation_engine(tmp_path) -> None:
    db = SQLiteAdapter(tmp_path / "val.db")
    val = OperationsValidationEngine(db, FrozenClock())
    r = val.validate_operation(operation_id="OP-V1",
        amount="500", description="pago proveedor")
    assert r["valid"] is True
    assert len(r["row_ids"]) == 2
    r2 = val.validate_operation(operation_id="OP-V2",
        amount="-5", description="")
    assert r2["valid"] is False
    s = val.summary()
    assert s["validations"] == 4
    assert s["successful"] == 2
    assert s["failed"] == 2
    print("OK validaciones: 4 chequeos persistidos (2 ok 2 fallo)")

def test_metrics_and_tracking(tmp_path) -> None:
    db = SQLiteAdapter(tmp_path / "met.db")
    clock = FrozenClock()
    ops = OperationsEngine(db, clock)
    metrics = OperationalMetricsEngine(db, clock)
    track = ProcessTrackingEngine(db, clock)
    op1 = ops.create_operation(company_id="ALC-01",
        operation_type="PAYMENT",
        description="Pago nomina", amount="2500.00")
    op2 = ops.create_operation(company_id="ALC-01",
        operation_type="COLLECTION",
        description="Cobro impuestos", amount="800.00")
    ops.transition(operation_id=op1["operation_id"],
        new_status="PENDING", actor="u")
    ops.transition(operation_id=op1["operation_id"],
        new_status="VALIDATED", actor="u")
    ops.transition(operation_id=op1["operation_id"],
        new_status="APPROVED", actor="u")
    ops.transition(operation_id=op1["operation_id"],
        new_status="IN_PROGRESS", actor="u")
    ops.transition(operation_id=op1["operation_id"],
        new_status="COMPLETED", actor="u")
    met = metrics.compute_company_metrics(
        company_id="ALC-01", period="2026-03")
    assert met["metrics"]["total_operations"] == "2"
    assert met["metrics"]["completed_operations"] == "1"
    assert met["metrics"]["active_amount"] == "2500.00"
    assert met["metrics"]["success_rate_pct"] == "50.0"
    stored = metrics.get_metrics("ALC-01", "2026-03")
    assert len(stored) == 4
    track.append_event(
        process_id=op1["operation_id"],
        event_type="NOTE", actor="contador",
        detail="asentado en libros")
    tl = track.get_timeline(op1["operation_id"])
    assert len(tl) == 1
    last = track.get_last_event(op1["operation_id"])
    assert last["event_type"] == "NOTE"
    assert track.event_count(
        op1["operation_id"]) == 1
    print("OK metricas+trazabilidad: persistidos Decimal")
