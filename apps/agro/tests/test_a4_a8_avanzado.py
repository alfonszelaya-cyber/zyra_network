import pytest
from shared_engines.storage.database import SQLiteAdapter
from apps.agro.modules.recursos_y_activos.tierras.land_geo_engine import (
    ensure_db as e4, set_geo_db, log_use_db,
    use_log_of_db, register_rotation_db,
    rotations_of_db, parcel_summary_db)
from apps.agro.modules.produccion.agricultura.agronomy_engine import (
    ensure_db as e5, add_input_db, inputs_of_db,
    report_pest_db, resolve_pest_db, pests_of_db,
    add_inspection_db, agronomic_summary_db)
from apps.agro.modules.produccion.planificacion.harvest_engine import (
    ensure_db as e6, register_harvest_db, add_lot_db,
    harvests_of_db, trace_of_lot_db, storage_load_db)
from apps.agro.modules.produccion.ganaderia.livestock_engine import (
    ensure_db as e7, register_animal_db, animal_of_db,
    animals_of_db, add_event_db, events_of_db,
    genealogy_of_db, livestock_summary_db)
from apps.agro.modules.recursos_y_activos.inventarios.inventory_batch_engine import (
    ensure_db as e8, add_batch_db, consume_db,
    stock_of_db, batches_of_db, moves_of_db,
    expired_of_db)


def test_a4_parcelas_geo_rotacion(tmp_path) -> None:
    db = SQLiteAdapter(tmp_path / "a4.db")
    e4(db)
    db.execute(
        "INSERT INTO agro_area_lands (land_id,"
        " producer_id, location, size_hectares,"
        " land_use, created_at) VALUES ('LND-1',"
        " 'P1', 'Zona Norte', 12.5, 'agricola',"
        " '2026-01-01')")
    with pytest.raises(LookupError):
        set_geo_db(db, land_id="NO",
                   coordinates="x")
    g = set_geo_db(db, land_id="LND-1",
        coordinates="13.98,-89.55",
        soil_type="franco", irrigation_access=True,
        area_effective=11.0, updated_at="2026-01-02")
    assert g["soil_type"] == "franco"
    assert g["irrigation_access"] is True
    log_use_db(db, land_id="LND-1", crop="MAIZ",
        season="2026-A", logged_at="2026-01-05")
    log_use_db(db, land_id="LND-1", crop="FRIJOL",
        season="2026-B", logged_at="2026-07-05")
    assert len(use_log_of_db(db, "LND-1")) == 2
    register_rotation_db(db, land_id="LND-1",
        crop_from="MAIZ", crop_to="FRIJOL",
        season_year="2027")
    assert len(rotations_of_db(db, "LND-1")) == 1
    s = parcel_summary_db(db, "P1")
    assert s["total"] == 1
    p = s["parcels"][0]
    assert p["uses"] == 2 and p["rotations"] == 1
    assert p["geo"]["soil_type"] == "franco"
    print("OK A-4: geo/riego/suelo + uso historico + rotacion + resumen")


def test_a5_insumos_plagas_inspecciones(tmp_path) -> None:
    db = SQLiteAdapter(tmp_path / "a5.db")
    e5(db)
    db.execute(
        "INSERT INTO agro_plans (plan_id, producer_id,"
        " unit_id, crop, target, status, created_at)"
        " VALUES ('PLN-1', 'P1', 'U-1', 'MAIZ', 100.0,"
        " 'growing', '2026-01-01')")
    with pytest.raises(LookupError):
        add_input_db(db, plan_id="NO", kind="SEMILLA",
                     product="x")
    with pytest.raises(ValueError):
        add_input_db(db, plan_id="PLN-1",
            kind="COMBUSTIBLE", product="x")
    add_input_db(db, plan_id="PLN-1", kind="SEMILLA",
        product="HB", dose=25.0, unit="lb")
    add_input_db(db, plan_id="PLN-1",
        kind="FERTILIZANTE", product="UREA",
        dose=50.0, unit="lb")
    assert len(inputs_of_db(db, "PLN-1")) == 2
    pl = report_pest_db(db, plan_id="PLN-1",
        pest_type="gusano", severity="alta",
        treatment="bio")
    resolve_pest_db(db, pl["pest_id"])
    with pytest.raises(ValueError):
        resolve_pest_db(db, pl["pest_id"])
    assert pests_of_db(db, "PLN-1")[0]["resolved"] \
        is True
    add_inspection_db(db, plan_id="PLN-1",
        inspector="ING-1", result="saludable")
    with pytest.raises(ValueError):
        add_inspection_db(db, plan_id="PLN-1",
            inspector="ING-1", result="")
    sm = agronomic_summary_db(db, "PLN-1")
    assert sm["inputs"] == 2
    assert sm["pests_open"] == 0
    assert sm["inspections"] == 1
    print("OK A-5: insumos + plagas cierre protegido + inspecciones + resumen")


def test_a6_cosecha_lotes_trazabilidad(tmp_path) -> None:
    db = SQLiteAdapter(tmp_path / "a6.db")
    e6(db)
    db.execute(
        "INSERT INTO agro_plans (plan_id, producer_id,"
        " unit_id, crop, target, status, created_at)"
        " VALUES ('PLN-2', 'P1', 'U-1', 'MAIZ', 100.0,"
        " 'harvested', '2026-01-01')")
    db.execute(
        "INSERT INTO agro_plans (plan_id, producer_id,"
        " unit_id, crop, target, status, created_at)"
        " VALUES ('PLN-3', 'P1', 'U-1', 'MAIZ', 10.0,"
        " 'cancelled', '2026-01-01')")
    with pytest.raises(LookupError):
        register_harvest_db(db, plan_id="NO",
            quantity=10)
    with pytest.raises(ValueError):
        register_harvest_db(db, plan_id="PLN-3",
            quantity=10)
    h = register_harvest_db(db, plan_id="PLN-2",
        quantity=90.0, unit="qq", quality_grade="A",
        losses=5.0, harvest_date="2026-04-20")
    assert h["producer_id"] == "P1"
    l1 = add_lot_db(db, harvest_id=h["harvest_id"],
        weight=60.0, grade="A", rejected=1.0,
        storage="BODEGA-CENTRAL")
    add_lot_db(db, harvest_id=h["harvest_id"],
        weight=25.0, grade="B",
        storage="BODEGA-CENTRAL")
    with pytest.raises(ValueError):
        add_lot_db(db,
            harvest_id=h["harvest_id"], weight=-1)
    tr = trace_of_lot_db(db, l1["lot_id"])
    assert tr["harvest"]["product"] == "MAIZ"
    assert tr["plan"]["plan_id"] == "PLN-2"
    assert len(harvests_of_db(db, "P1")) == 1
    load = storage_load_db(db, "BODEGA-CENTRAL")
    assert load["by_product"][0]["weight"] == 85.0
    assert load["by_product"][0]["rejected"] == 1.0
    print("OK A-6: cosecha (cancelado rechazado) + lotes + trazabilidad plan->cosecha->lote + carga almacen")


def test_a7_ganaderia_expediente_eventos(tmp_path) -> None:
    db = SQLiteAdapter(tmp_path / "a7.db")
    e7(db)
    with pytest.raises(ValueError):
        register_animal_db(db, producer_id="P1",
            species=" ")
    toro = register_animal_db(db, producer_id="P1",
        species="BOVINO", breed="simmental",
        created_at="2026-01-01")
    with pytest.raises(LookupError):
        register_animal_db(db, producer_id="P1",
            species="BOVINO", sire_id="NO")
    vaca = register_animal_db(db, producer_id="P1",
        species="BOVINO", created_at="2026-01-01")
    bec = register_animal_db(db, producer_id="P1",
        species="BOVINO",
        sire_id=toro["animal_id"],
        dam_id=vaca["animal_id"])
    gen = genealogy_of_db(db, bec["animal_id"])
    assert gen["sire"]["animal_id"] \
        == toro["animal_id"]
    assert gen["dam"]["animal_id"] \
        == vaca["animal_id"]
    add_event_db(db, animal_id=toro["animal_id"],
        kind="VACUNA", detail="aftosa")
    add_event_db(db, animal_id=toro["animal_id"],
        kind="PESO", value=450.5)
    assert len(events_of_db(db,
                            toro["animal_id"])) == 2
    with pytest.raises(ValueError):
        add_event_db(db,
            animal_id=toro["animal_id"],
            kind="BAÑO")
    add_event_db(db, animal_id=toro["animal_id"],
        kind="MUERTE")
    assert animal_of_db(
        db, toro["animal_id"])["status"] == "muerto"
    with pytest.raises(ValueError):
        add_event_db(db,
            animal_id=toro["animal_id"],
            kind="PESO", value=1)
    assert len(animals_of_db(db, "P1",
                             status="vivo")) == 2
    sm = livestock_summary_db(db, "P1")
    assert sm["by_species"]["BOVINO"]["vivos"] == 2
    assert sm["by_species"]["BOVINO"]["muertos"] == 1
    print("OK A-7: expediente + genealogia verificada + eventos + MUERTE bloquea + resumen")


def test_a8_fifo_fefo_vencidos(tmp_path) -> None:
    db = SQLiteAdapter(tmp_path / "a8.db")
    e8(db)
    with pytest.raises(ValueError):
        add_batch_db(db, producer_id="P1",
            product="MAIZ", quantity=0)
    b1 = add_batch_db(db, producer_id="P1",
        product="MAIZ", quantity=10.0, unit="qq",
        created_at="2026-01-01")
    b2 = add_batch_db(db, producer_id="P1",
        product="MAIZ", quantity=5.0,
        expiry_date="2026-03-01",
        created_at="2026-01-02")
    b3 = add_batch_db(db, producer_id="P1",
        product="MAIZ", quantity=8.0,
        expiry_date="2026-02-01",
        created_at="2026-01-03")
    b4 = add_batch_db(db, producer_id="P1",
        product="MAIZ", quantity=2.0,
        created_at="2026-01-04")
    with pytest.raises(ValueError):
        consume_db(db, producer_id="P1",
            product="MAIZ", quantity=1,
            policy="LIFO")
    with pytest.raises(ValueError):
        consume_db(db, producer_id="P1",
            product="MAIZ", quantity=26,
            policy="FIFO")
    ok_exacto = consume_db(db, producer_id="P1",
        product="MAIZ", quantity=25,
        policy="FIFO", reason="venta total")
    assert ok_exacto["consumed"] == 25.0
    db.execute(
        "UPDATE agro_inventory_batches SET quantity ="
        " 10.0 WHERE batch_id = ?",
        (b1["batch_id"],))
    db.execute(
        "UPDATE agro_inventory_batches SET quantity ="
        " 5.0 WHERE batch_id = ?",
        (b2["batch_id"],))
    db.execute(
        "UPDATE agro_inventory_batches SET quantity ="
        " 8.0 WHERE batch_id = ?",
        (b3["batch_id"],))
    db.execute(
        "UPDATE agro_inventory_batches SET quantity ="
        " 2.0 WHERE batch_id = ?",
        (b4["batch_id"],))
    r = consume_db(db, producer_id="P1",
        product="MAIZ", quantity=12.0,
        policy="FIFO", reason="venta")
    assert r["from_batches"][0]["batch_id"] \
        == b1["batch_id"]
    assert r["from_batches"][0]["taken"] == 10.0
    assert r["from_batches"][1]["taken"] == 2.0
    rows = {b["batch_id"]: b
            for b in batches_of_db(db, "P1")}
    assert rows[b1["batch_id"]]["quantity"] == 0.0
    assert rows[b2["batch_id"]]["quantity"] == 3.0
    r2 = consume_db(db, producer_id="P1",
        product="MAIZ", quantity=4.0,
        policy="FEFO", reason="venta")
    assert r2["from_batches"][0]["batch_id"] \
        == b3["batch_id"]
    mv = moves_of_db(db, b1["batch_id"])
    assert mv[0]["direction"] == "IN"
    assert mv[1]["direction"] == "OUT"
    exp = expired_of_db(db, "P1", as_of="2026-03-15")
    ids = [e["batch_id"] for e in exp]
    assert b2["batch_id"] in ids
    assert b3["batch_id"] in ids
    assert b4["batch_id"] not in ids
    print("OK A-8: stock insuficiente (26>25) rechazado + pedir EXACTO (25=25) legitimo + restock + FIFO por entrada (10+2) + FEFO por vencimiento (b3 antes que b2) + vencidos b2/b3 con b4 sin expiry excluido + movimientos")
