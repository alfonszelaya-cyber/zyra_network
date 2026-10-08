import pytest
from shared_engines.storage.database import SQLiteAdapter
from apps.axis.life_history.immigration_registry import (
    ensure_db as e10, register_move_db, moves_of_db,
    apply_visa_db, decide_visa_db, expire_visa_db,
    grant_residency_db, naturalize_db,
    order_deportation_db, execute_deportation_db,
    deportations_of_db)
from apps.axis.life_history.police_registry import (
    ensure_db as e6)
from apps.axis.life_history.border_control import (
    ensure_db as e11, register_post_db,
    register_bagent_db, cross_db, crosses_of_db,
    flag_vehicle_db, vehicle_status_db, inspect_db,
    inspections_of_db)
from apps.axis.life_history.prison_movements import (
    ensure_db as e12, classify_db, transfer_db,
    visit_db, release_here_db, movements_of_db,
    visits_of_db)
from apps.axis.life_history.intelligence_desk import (
    ensure_db as e13, register_source_db,
    file_report_db, register_entity_db,
    link_entities_db, correlations_of_db)
from apps.axis.life_history.emergency_dispatch import (
    ensure_db as e15, report_incident_db,
    register_resource_db, available_resources_db,
    dispatch_db, resolve_incident_db)


def test_ax10_migracion_completa(tmp_path) -> None:
    db = SQLiteAdapter(tmp_path / "m.db")
    e10(db)
    with pytest.raises(ValueError):
        register_move_db(db, person_id=" ",
            kind="ENTRADA")
    mv = register_move_db(db, person_id="P-1",
        zid="ZID-1", kind="ENTRADA",
        checkpoint="AEROPUERTO-SS",
        at="2026-01-01")
    assert mv["kind"] == "ENTRADA"
    with pytest.raises(ValueError):
        register_move_db(db, person_id="P-1",
            kind="CRUCE")
    assert len(moves_of_db(db, "P-1")) == 1
    v = apply_visa_db(db, person_id="P-1",
        kind="TURISTA", notes="90 dias",
        at="2026-01-02")
    with pytest.raises(ValueError):
        apply_visa_db(db, person_id="P-1",
            kind="ESPACIAL")
    d = decide_visa_db(db, v["visa_id"],
        approve=True, expires_at="2026-04-02",
        at="2026-01-03")
    assert d["status"] == "aprobada"
    with pytest.raises(ValueError):
        decide_visa_db(db, v["visa_id"],
            approve=False)
    vx = expire_visa_db(db, v["visa_id"],
        at="2026-04-03")
    assert vx["status"] == "vencida"
    with pytest.raises(ValueError):
        expire_visa_db(db, v["visa_id"])
    r = grant_residency_db(db, person_id="P-1",
        kind="TEMPORAL", at="2026-01-05")
    assert r["status"] == "vigente"
    assert naturalize_db(db, person_id="P-1",
        granted_by="MIGRACION")["status"] \
        == "naturalizado"
    with pytest.raises(ValueError):
        naturalize_db(db, person_id="P-1",
            granted_by="MIGRACION")
    dep = order_deportation_db(db, person_id="P-2",
        reason="sobrepaso", ordered_by="MIG-1",
        at="2026-01-06")
    with pytest.raises(ValueError):
        order_deportation_db(db, person_id="P-2",
            reason=" ", ordered_by="MIG-1")
    ex = execute_deportation_db(db,
        dep["dep_id"], at="2026-01-07")
    assert ex["status"] == "ejecutada"
    with pytest.raises(ValueError):
        execute_deportation_db(db, dep["dep_id"])
    assert len(deportations_of_db(db, "P-2")) == 1
    print("OK AX-10: visas ciclo + residencia + ciudadania sin duplicado + deportacion unica")


def test_ax11_fronteras_cruces_alerta(tmp_path) -> None:
    db = SQLiteAdapter(tmp_path / "b.db")
    e6(db)
    e11(db)
    db.execute(
        "INSERT INTO ax_pol_wanted (wanted_id,"
        " person_id, zid, reason, ref_case_id,"
        " status, requested_by, created_at)"
        " VALUES ('AXW-TEST', 'P-SOS', 'ZID-SOS',"
        " 'captura C1', 'C1', 'buscado', 'J1',"
        " '2026')")
    post = register_post_db(db, name="LA HACHADURA",
        created_at="2026")
    with pytest.raises(ValueError):
        register_post_db(db, name=" ",
            kind="espacial")
    ag = register_bagent_db(db,
        name="Agente Frontera",
        post_id=post["post_id"])
    with pytest.raises(ValueError):
        cross_db(db, post_id=post["post_id"],
            direction="LATERAL", zid="ZID-1")
    with pytest.raises(ValueError):
        cross_db(db, post_id=post["post_id"],
            direction="ENTRADA")
    c1 = cross_db(db, post_id=post["post_id"],
        direction="ENTRADA", person_id="P-1",
        zid="ZID-CLEAN", agent_id=ag["agent_id"],
        at="2026-01-01")
    assert c1["alert"] == ""
    c2 = cross_db(db, post_id=post["post_id"],
        direction="ENTRADA", person_id="P-SOS",
        zid="ZID-SOS", agent_id=ag["agent_id"],
        at="2026-01-02")
    assert c2["alert"].startswith("BUSCADO:")
    alerts = crosses_of_db(db, only_alerts=True)
    assert len(alerts) == 1
    flag_vehicle_db(db, plate="p-123-456",
        reason="robo reportado")
    vs = vehicle_status_db(db, "p-123-456")
    assert vs["flagged_bool"] is True
    vs2 = vehicle_status_db(db, "P-999-999")
    assert vs2["flagged_bool"] is False
    inspect_db(db, veh_id="X", result="ok",
        agent_id=ag["agent_id"])
    with pytest.raises(ValueError):
        inspect_db(db, result="solo result")
    with pytest.raises(ValueError):
        inspect_db(db, veh_id="X", result=" ")
    assert len(inspections_of_db(db, "X")) == 1
    print("OK AX-11: puestos/agentes + cruces con ALERTA de buscado (ZID) + vehiculos + inspecciones")


def test_ax12_prison_movimientos(tmp_path) -> None:
    db = SQLiteAdapter(tmp_path / "pm.db")
    e12(db)
    db.execute(
        "INSERT INTO ax_justice_pris (pris_id,"
        " case_id, person_id, zid, sentence_days,"
        " status, entry_by, entry_at, exit_at)"
        " VALUES ('AXP-1', 'C1', 'P-1', 'ZID-1',"
        " 365, 'preso', 'CENTRO-1', '2026-01-01',"
        " '')")
    cl = classify_db(db, "AXP-1", risk="MEDIO",
        center="PENAL-CENTRAL", at="2026-01-02")
    assert cl["risk"] == "MEDIO"
    assert cl["center"] == "PENAL-CENTRAL"
    with pytest.raises(ValueError):
        classify_db(db, "AXP-1", risk="EXTREMO",
            center="X")
    tr = transfer_db(db, "AXP-1",
        from_center="PENAL-CENTRAL",
        to_center="PENAL-SUR", at="2026-02-01")
    assert tr["kind"] == "TRASLADO"
    assert tr["to_center"] == "PENAL-SUR"
    with pytest.raises(ValueError):
        transfer_db(db, "AXP-1",
            from_center="A", to_center=" ")
    visit_db(db, "AXP-1", visitor="FAMILIAR-1",
             at="2026-02-05")
    with pytest.raises(ValueError):
        visit_db(db, "AXP-1", visitor=" ")
    rl = release_here_db(db, "AXP-1",
        at="2027-01-01")
    assert rl["status"] == "libre"
    with pytest.raises(ValueError):
        transfer_db(db, "AXP-1",
            from_center="X", to_center="Y")
    with pytest.raises(ValueError):
        visit_db(db, "AXP-1", visitor="TARDE")
    mv = movements_of_db(db, "AXP-1")
    kinds = [m["kind"] for m in mv]
    assert kinds == ["CLASIFICACION", "TRASLADO",
                     "LIBERACION"]
    assert mv[1]["to_center"] == "PENAL-SUR"
    assert len(visits_of_db(db, "AXP-1")) == 1
    print("OK AX-12: clasificacion + traslado (return verificado contra engine v3 con to_center) + visitas + liberacion sincroniza + historial")


def test_ax13_inteligencia_correlacion(tmp_path) -> None:
    db = SQLiteAdapter(tmp_path / "i.db")
    e13(db)
    s = register_source_db(db, codename="AGUILA",
        reliability="alta", created_at="2026")
    with pytest.raises(ValueError):
        register_source_db(db, codename=" ")
    rep = file_report_db(db, source_id=s["source_id"],
        body="movimiento sospechoso en puerto",
        classification="SECRETO",
        filed_by="ANALISTA-1", at="2026-01-01")
    assert rep["classification"] == "SECRETO"
    with pytest.raises(ValueError):
        file_report_db(db, source_id=s["source_id"],
            body=" ")
    with pytest.raises(ValueError):
        file_report_db(db, source_id=s["source_id"],
            body="x", classification="PUBLICO")
    ent1 = register_entity_db(db, kind="PERSONA",
        name="Sujeto X", zid="ZID-X",
        created_at="2026")
    ent2 = register_entity_db(db,
        kind="ORGANIZACION", name="Red Y",
        created_at="2026")
    with pytest.raises(ValueError):
        register_entity_db(db, kind="ALIEN",
            name="Z")
    lk = link_entities_db(db, ent_a=ent1["ent_id"],
        ent_b=ent2["ent_id"],
        relation="opera para", created_at="2026")
    assert lk["link_id"]
    assert lk["relation"] == "opera para"
    with pytest.raises(ValueError):
        link_entities_db(db, ent_a=ent1["ent_id"],
            ent_b=ent1["ent_id"])
    with pytest.raises(LookupError):
        link_entities_db(db, ent_a="NO",
            ent_b=ent2["ent_id"])
    cor = correlations_of_db(db, ent1["ent_id"])
    assert cor["entity"]["zid"] == "ZID-X"
    assert cor["links"][0]["relation"] \
        == "opera para"
    print("OK AX-13: fuentes + informes SECRETO + entidades ZID + vinculos (LookupError inexistentes) + correlacion")
