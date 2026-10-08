import pytest
from shared_engines.common.clocks import FrozenClock
from shared_engines.storage.database import SQLiteAdapter
from apps.agro.modules.recursos_y_activos.maquinaria.machinery_ops_engine import (
    ensure_db as e9, log_usage_db, log_maintenance_db,
    open_order_db, close_order_db, summary_of_db)
from apps.agro.modules.recursos_y_activos.recursos_hidricos.water_ops_engine import (
    ensure_db as e10, register_use_db, schedule_db,
    balance_of_db, sched_of_db)
from apps.agro.modules.comercializacion.contracts_engine import (
    ensure_db as e11, create_contract_db,
    advance_contract_db, cancel_contract_db,
    add_purchase_order_db, liquidate_db,
    contracts_of_db)
from apps.agro.modules.comercializacion.exportacion.export_docs_engine import (
    ensure_db as e12, open_file_db, add_doc_db,
    ready_db, dispatch_db, exports_of_db_full)
from apps.agro.modules.riesgo.agro_risk_unified import (
    evaluate_db, history_of_db, worst_of_db)
from apps.agro.modules.gobierno.aid_governance_engine import (
    ensure_db as e14, create_request_checked_db,
    set_eligibility_db, decide_db,
    duplicates_of_db, impact_metrics_db)


def test_a9_maquinaria_uso_mantenimiento_ordenes(tmp_path) -> None:
    db = SQLiteAdapter(tmp_path / "a9.db")
    e9(db)
    from apps.agro.infrastructure.persistence.agro_area_store import (
        AgroAreaStore,
    )
    mid = AgroAreaStore(db, FrozenClock()).add_machinery(
        producer_id="P1", machine_type="tractor",
        description="John Deere")["machine_id"]
    with pytest.raises(LookupError):
        log_usage_db(db, machine_id="NO", hours=1)
    log_usage_db(db, machine_id=mid, hours=4.5,
        fuel_liters=12.0, operator="OP-1")
    log_usage_db(db, machine_id=mid, hours=3.5,
        fuel_liters=10.0)
    log_maintenance_db(db, machine_id=mid,
        kind="PREVENTIVA", detail="aceite",
        cost="45.505", done_at="2026-02-01")
    with pytest.raises(ValueError):
        log_maintenance_db(db, machine_id=mid,
            kind="RUTINARIA")
    o = open_order_db(db, machine_id=mid,
        task="cambio llantas")
    c = close_order_db(db, o["order_id"], ok=True,
        closed_at="2026-02-10")
    assert c["status"] == "done"
    with pytest.raises(ValueError):
        close_order_db(db, o["order_id"])
    s = summary_of_db(db, mid)
    assert s["hours_total"] == 8.0
    assert s["fuel_total"] == 22.0
    assert s["maintenance_cost"] == 45.51
    assert s["open_orders"] == 0
    print("OK A-9: horas/combustible + mantenimiento (costo 2d) + ordenes con cierre unico + resumen")


def test_a10_riego_balance(tmp_path) -> None:
    db = SQLiteAdapter(tmp_path / "a10.db")
    e10(db)
    db.execute(
        "INSERT INTO agro_area_water (water_id,"
        " producer_id, source_type, capacity_liters,"
        " created_at) VALUES ('WTR-1', 'P1', 'pozo',"
        " 1000.0, 0)")
    with pytest.raises(LookupError):
        register_use_db(db, water_id="NO",
            volume_liters=1)
    with pytest.raises(ValueError):
        register_use_db(db, water_id="WTR-1",
            volume_liters=1001)
    u = register_use_db(db, water_id="WTR-1",
        volume_liters=400.0, purpose="riego maiz")
    assert u["remaining_after"] == 600.0
    schedule_db(db, water_id="WTR-1", weekday="LUN",
        volume_planned=250.0)
    with pytest.raises(ValueError):
        schedule_db(db, water_id="WTR-1",
            weekday="DOMINGO", volume_planned=1)
    assert len(sched_of_db(db, "WTR-1")) == 1
    b = balance_of_db(db, "WTR-1")
    assert b["capacity"] == 1000.0
    assert b["used"] == 400.0
    assert b["remaining"] == 600.0
    assert b["covers_week"] is True
    print("OK A-10: consumo con sobre-consumo rechazado + programacion semanal + balance covers_week")


def test_a11_contratos_oc_liquidacion(tmp_path) -> None:
    db = SQLiteAdapter(tmp_path / "a11.db")
    e11(db)
    c = create_contract_db(db, producer_id="P1",
        buyer="EXPORT-SA", product="MAIZ",
        quantity=100.0, unit="qq", price="25.005",
        currency="USD", created_at="2026-01-01")
    cid = c["contract_id"]
    with pytest.raises(ValueError):
        cancel_contract_db(db, cid)
    cancel_contract_db(db, cid, reason="prueba")
    c2 = create_contract_db(db, producer_id="P1",
        buyer="EXPORT-SA", product="FRIJOL",
        quantity=50.0, unit="qq", price="40.00",
        created_at="2026-01-02")
    cid2 = c2["contract_id"]
    with pytest.raises(ValueError):
        add_purchase_order_db(db, contract_id=cid2,
            po_number="PO-1", quantity=10,
            amount=400)
    advance_contract_db(db, cid2, actor="P1")
    with pytest.raises(ValueError):
        liquidate_db(db, cid2)
    po = add_purchase_order_db(db,
        contract_id=cid2, po_number="PO-1",
        quantity=10, amount=400.0)
    assert po["amount"] == 400.0
    advance_contract_db(db, cid2,
        sale_id="SALP-TEST")
    liq = liquidate_db(db, cid2, deductions=50.0)
    assert liq["gross"] == 2000.0
    assert liq["net"] == 1950.0
    with pytest.raises(ValueError):
        liquidate_db(db, cid2, deductions=50.0)
    rows = contracts_of_db(db, "P1")
    st = {r["contract_id"]: r["status"]
          for r in rows}
    assert st[cid] == "cancelled"
    assert st[cid2] == "liquidated"
    print("OK A-11: contratos draft->signed->delivered->liquidated + cancel solo pre-signed + OC exige signed + liquidacion neto 2d")


def test_a12_exportacion_expediente(tmp_path) -> None:
    db = SQLiteAdapter(tmp_path / "a12.db")
    e12(db)
    from apps.agro.modules.produccion.planificacion.harvest_engine import (
        ensure_db as e6h,
    )
    e6h(db)
    db.execute(
        "INSERT INTO agro_harvest_lots (lot_id,"
        " harvest_id, weight, grade, rejected,"
        " storage, created_at) VALUES ('LOT-OK',"
        " 'HRV-1', 500.0, 'A', 0, 'BODEGA', '2026')")
    with pytest.raises(LookupError):
        open_file_db(db, producer_id="P1",
            destination="USA", lot_id="NO")
    e = open_file_db(db, producer_id="P1",
        destination="USA", product="MAIZ",
        quantity=500.0, lot_id="LOT-OK")
    eid = e["exp_id"]
    with pytest.raises(ValueError):
        ready_db(db, eid)
    with pytest.raises(ValueError):
        dispatch_db(db, eid, carrier="MAERSK")
    add_doc_db(db, exp_id=eid, kind="PHYTO",
        ref="PHY-1")
    with pytest.raises(ValueError):
        add_doc_db(db, exp_id=eid,
            kind="INVALIDA")
    add_doc_db(db, exp_id=eid, kind="CO",
        ref="CO-1")
    r = ready_db(db, eid)
    assert r["status"] == "ready"
    d = dispatch_db(db, eid, carrier="MAERSK",
        container="MSCU-123", dispatched_at="2026")
    assert d["status"] == "dispatched"
    full = exports_of_db_full(db, "P1")
    assert full[0]["status"] == "dispatched"
    assert len(full[0]["docs"]) == 2
    assert full[0]["carrier"] == "MAERSK"
    print("OK A-12: expediente con lote verificado + docs (min 2 para ready) + despacho requiere ready + vista completa")


def test_a13_riesgo_agricola_unificado(tmp_path) -> None:
    db = SQLiteAdapter(tmp_path / "a13.db")
    r = evaluate_db(db, producer_id="P1",
        event_type="sequia", severity="alta",
        losses=50.0, production=100.0,
        affected_units=20.0, total_units=40.0,
        recovered=20.0, created_at=1.0)
    assert r["score"] == 100
    assert r["level"] == "CRITICAL"
    kinds = {c["kind"] for c in r["components"]}
    assert kinds == {"CLIMA", "PRODUCTIVO",
                     "IMPACTO", "RESILIENCIA"}
    assert r["not_evaluated"] == []
    r2 = evaluate_db(db, producer_id="P1",
        event_type="lluvia", severity="baja",
        created_at=2.0)
    assert r2["score"] == 10
    assert r2["level"] == "LOW"
    assert any("PRODUCTIVO" in s
               for s in r2["not_evaluated"])
    r3 = evaluate_db(db, producer_id="P2",
        event_type="helada", severity="media",
        created_at=3.0)
    assert r3["score"] == 30
    assert r3["level"] == "MEDIUM"
    h = history_of_db(db, "P1")
    assert len(h) == 2
    w = worst_of_db(db)
    assert w[0]["producer_id"] == "P1"
    assert w[0]["worst"] == 100
    print("OK A-13: formula transparente (60+50+50-20=140->100 CRITICAL; baja=10 LOW) + not_evaluated honesto + historial + peores")


def test_a14_ayuda_elegibilidad_duplicados_impacto(tmp_path) -> None:
    db = SQLiteAdapter(tmp_path / "a14.db")
    e14(db)
    a1 = create_request_checked_db(db,
        producer_id="P1", program="semillas",
        item="maiz", quantity=10.0, now=1.0)
    with pytest.raises(ValueError):
        create_request_checked_db(db,
            producer_id="P1", program="semillas",
            item="maiz", quantity=5.0, now=2.0)
    with pytest.raises(ValueError):
        decide_db(db, aid_id=a1["aid_id"],
            approve=True)
    with pytest.raises(ValueError):
        set_eligibility_db(db,
            aid_id=a1["aid_id"], eligible=True,
            reason=" ")
    set_eligibility_db(db, aid_id=a1["aid_id"],
        eligible=True, reason="cumple requisitos",
        now=3.0)
    d = decide_db(db, aid_id=a1["aid_id"],
        approve=True, now=4.0)
    assert d["status"] == "approved"
    with pytest.raises(ValueError):
        set_eligibility_db(db,
            aid_id=a1["aid_id"],
            eligible=False, reason="tarde",
            now=5.0)
    a2 = create_request_checked_db(db,
        producer_id="P1", program="fertilizante",
        item="urea", quantity=8.0, now=6.0)
    set_eligibility_db(db, aid_id=a2["aid_id"],
        eligible=False, reason="fuera de programa",
        now=7.0)
    with pytest.raises(ValueError):
        decide_db(db, aid_id=a2["aid_id"],
            approve=True)
    m = impact_metrics_db(db)
    assert m["by_status"]["approved"]["n"] == 1
    assert m["by_status"]["requested"]["n"] == 1
    assert m["total"] == 2
    dups = duplicates_of_db(db,
        producer_id="P1", program="semillas",
        item="maiz")
    assert len(dups) == 1
    assert dups[0]["status"] == "approved"
    print("OK A-14: duplicados bloquean + decide exige ELIGIBLE + motivo obligatorio + metricas de impacto")
