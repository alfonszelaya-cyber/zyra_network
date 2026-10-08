import pytest
from shared_engines.storage.database import SQLiteAdapter
from apps.axis.life_history.justice_extended import (
    ensure_db as e4, issue_resolucion_db, res_of_db,
    file_recurso_db, resolve_recurso_db,
    issue_medida_db, lift_medida_db, issue_orden_db,
    execute_orden_db, send_mail_db, mail_of_db,
    imprison_db, release_prision_db, condenados_db,
    estado_procesos_db)


def test_resoluciones_recursos_medidas(tmp_path) -> None:
    db = SQLiteAdapter(tmp_path / "j1.db")
    e4(db)
    with pytest.raises(ValueError):
        issue_resolucion_db(db, case_id="C1",
            kind="INVALIDA", judge="J1")
    r = issue_resolucion_db(db, case_id="C1",
        kind="SENTENCIA", judge="JUEZ-PENAL",
        body="condena parcial",
        issued_at="2026-01-01")
    assert r["kind"] == "SENTENCIA"
    assert len(res_of_db(db, "C1")) == 1
    with pytest.raises(ValueError):
        file_recurso_db(db, case_id="C1",
            kind="APELACION", base=" ",
            filed_by="AB-1")
    rec = file_recurso_db(db, case_id="C1",
        kind="APELACION", base="error de derecho",
        filed_by="AB-1", created_at="2026-01-05")
    assert rec["outcome"] == "pendiente"
    with pytest.raises(ValueError):
        resolve_recurso_db(db, rec["rec_id"],
            outcome="OTRA", resolved_by="J2")
    rr = resolve_recurso_db(db, rec["rec_id"],
        outcome="CONFIRMADA", resolved_by="J2")
    assert rr["outcome"] == "CONFIRMADA"
    with pytest.raises(ValueError):
        resolve_recurso_db(db, rec["rec_id"],
            outcome="REVOCADA",
            resolved_by="J2")
    m = issue_medida_db(db, case_id="C1",
        kind="PRISION_PREVENTIVA",
        target_person="P-1", detail="riesgo fuga",
        issued_by="JUEZ-1")
    with pytest.raises(ValueError):
        issue_medida_db(db, case_id="C1",
            kind="OTRA", target_person="P-1")
    lift = lift_medida_db(db, m["med_id"],
        lifted_at="2026-02-01")
    assert lift["status"] == "levantada"
    with pytest.raises(ValueError):
        lift_medida_db(db, m["med_id"])
    print("OK AX-4a: resoluciones + recursos + medidas")


def test_ordenes_correspondencia_prision_estado(tmp_path) -> None:
    db = SQLiteAdapter(tmp_path / "j2.db")
    e4(db)
    with pytest.raises(ValueError):
        issue_orden_db(db, kind="ORDEN_CAPTURA",
            issued_by="J1")
    o = issue_orden_db(db, kind="ORDEN_CAPTURA",
        target_person="P-9", case_id="C1",
        issued_by="J1", issued_at="2026-01-02")
    ex = execute_orden_db(db, o["ord_id"],
        executed_by="POL-1",
        executed_at="2026-01-03")
    assert ex["status"] == "ejecutada"
    with pytest.raises(ValueError):
        execute_orden_db(db, o["ord_id"],
            executed_by="POL-2")
    m = send_mail_db(db, to_account="AB-1",
        subject="audiencia viernes 9am",
        case_id="C1", sent_at="2026-01-04")
    assert m["mail_id"]
    assert len(mail_of_db(db, "AB-1")) == 1
    with pytest.raises(ValueError):
        send_mail_db(db, to_account="",
            subject="x")
    with pytest.raises(ValueError):
        imprison_db(db, case_id="SIN-SENT",
            person_id="P-1", zid="ZID-1",
            sentence_days=365)
    issue_resolucion_db(db, case_id="C1",
        kind="SENTENCIA", judge="JUEZ-PENAL",
        issued_at="2026-01-10")
    pr = imprison_db(db, case_id="C1",
        person_id="P-1", zid="ZID-1",
        sentence_days=365, entry_by="CENTRO-1",
        entry_at="2026-01-11")
    assert pr["status"] == "preso"
    with pytest.raises(ValueError):
        imprison_db(db, case_id="C1",
            person_id="P-1", sentence_days=-5)
    act = condenados_db(db)
    assert len(act) == 1
    assert act[0]["zid"] == "ZID-1"
    rl = release_prision_db(db, pr["pris_id"],
        exit_at="2027-01-11")
    assert rl["status"] == "libre"
    assert condenados_db(db) == []
    assert len(condenados_db(
        db, only_activos=False)) == 1
    est = estado_procesos_db(db, case_id="C1")
    e = est[0]
    assert e["resoluciones"] == 1
    assert e["ordenes"] == 1
    assert e["prision"] == "libre"
    print("OK AX-4b: ordenes (doble ejecucion rechazada) + correspondencia (regla 79) + prision exige sentencia con ZID + estado")


def test_estado_todos_los_casos(tmp_path) -> None:
    db = SQLiteAdapter(tmp_path / "j3.db")
    e4(db)
    issue_resolucion_db(db, case_id="CA",
        kind="AUTO", judge="J1")
    issue_resolucion_db(db, case_id="CB",
        kind="DECRETO", judge="J1")
    allst = estado_procesos_db(db)
    ids = [x["case_id"] for x in allst]
    assert ids == ["CA", "CB"]
    print("OK AX-4c: estado consolidado")
