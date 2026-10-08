import pytest
from shared_engines.storage.database import SQLiteAdapter
from apps.axis.life_history.health_ehr import (
    ensure_db as e5, add_record_db, records_of_db,
    add_prescription_db, ehr_summary_db)
from apps.axis.life_history.police_registry import (
    ensure_db as e6, register_agent_db, agents_of_db,
    file_denuncia_db, advance_denuncia_db,
    register_wanted_db, wanted_active_db, capture_db,
    release_capture_db)
from apps.axis.life_history.criminal_record import (
    ensure_db as e7, open_criminal_case_db,
    add_charge_db, convict_db,
    antecedentes_verify_db, antecedentes_cert_db,
    reincidence_db)
from apps.axis.life_history.forensic_lab import (
    ensure_db as e8, open_fx_db, add_finding_db,
    issue_report_db, fxs_by_ref_db)
from apps.axis.life_history.evidence_vault import (
    ensure_db as e9, ingest_db, transfer_db,
    analyze_db, present_db, release_db,
    custody_of_db, custody_verified_db)


def test_ax5_ehr_completo(tmp_path) -> None:
    db = SQLiteAdapter(tmp_path / "h.db")
    e5(db)
    with pytest.raises(ValueError):
        add_record_db(db, person_id="P-1",
            kind="INVALIDA", detail="x")
    with pytest.raises(ValueError):
        add_record_db(db, person_id="P-1",
            kind="DIAGNOSTICO", detail=" ")
    add_record_db(db, person_id="P-1",
        kind="DIAGNOSTICO", detail="diabetes tipo 2",
        code="E11", actor="MED-1")
    add_record_db(db, person_id="P-1",
        kind="ALERGIA", detail="penicilina")
    add_record_db(db, person_id="P-1",
        kind="VACUNA", detail="influenza 2026")
    add_record_db(db, person_id="P-1",
        kind="CRONICO", detail="hipertension")
    assert len(records_of_db(db, "P-1")) == 4
    assert len(records_of_db(db, "P-1",
        kind="ALERGIA")) == 1
    add_prescription_db(db, person_id="P-1",
        medication="metformina", dose="850mg",
        days=30, prescribed_by="MED-1",
        issued_at="2026-01-01")
    s = ehr_summary_db(db, "P-1")
    assert s["by_kind"]["DIAGNOSTICO"] == 1
    assert s["allergies"] == ["penicilina"]
    assert s["chronic"] == ["hipertension"]
    assert s["prescriptions"] == 1
    print("OK AX-5: EHR completo + recetas + resumen")


def test_ax6_policia_busquedas_capturas(tmp_path) -> None:
    db = SQLiteAdapter(tmp_path / "p.db")
    e6(db)
    ag = register_agent_db(db, name="Agente Ruiz",
        unit="ZONA-4", created_at="2026-01-01")
    with pytest.raises(ValueError):
        register_agent_db(db, name=" ")
    assert len(agents_of_db(db)) == 1
    with pytest.raises(ValueError):
        file_denuncia_db(db, complainant="X",
            facts=" ")
    den = file_denuncia_db(db,
        complainant="VECINO-1",
        against_person="SOSPECHOSO-1",
        facts="robo reportado",
        police_actor="AX-AG",
        created_at="2026-01-02")
    d1 = advance_denuncia_db(db, den["den_id"],
        police_actor="AG-1")
    assert d1["status"] == "investigacion"
    d2 = advance_denuncia_db(db, den["den_id"])
    assert d2["status"] == "cerrada"
    with pytest.raises(ValueError):
        advance_denuncia_db(db, den["den_id"])
    with pytest.raises(ValueError):
        register_wanted_db(db, reason="robo")
    w = register_wanted_db(db,
        person_id="P-SOS", zid="ZID-SOS",
        reason="orden de captura C1",
        ref_case_id="C1", requested_by="J1",
        created_at="2026-01-03")
    assert len(wanted_active_db(db)) == 1
    with pytest.raises(ValueError):
        capture_db(db, w["wanted_id"],
            by_agent=" ")
    cap = capture_db(db, w["wanted_id"],
        by_agent=ag["agent_id"],
        captured_at="2026-01-05")
    assert wanted_active_db(db) == []
    rel = release_capture_db(db, cap["cap_id"],
        released_at="2026-02-05")
    assert rel["released"] is True
    with pytest.raises(ValueError):
        release_capture_db(db, cap["cap_id"])
    print("OK AX-6: agentes + denuncias + buscados con ZID + captura + liberacion unica")


def test_ax7_criminal_antecedentes_hashchain(tmp_path) -> None:
    db = SQLiteAdapter(tmp_path / "c.db")
    e7(db)
    with pytest.raises(ValueError):
        open_criminal_case_db(db, person_id=" ",
            zid="ZID-1")
    c1 = open_criminal_case_db(db,
        person_id="P-ACUS", zid="ZID-ACUS",
        ref_case_id="JC-pen-1",
        created_at="2026-01-01")
    ch = add_charge_db(db, crim_id=c1["crim_id"],
        charge="robo agravado", detail="art. 203")
    assert ch["charge_id"]
    with pytest.raises(ValueError):
        add_charge_db(db, crim_id=c1["crim_id"],
            charge=" ")
    conv = convict_db(db, crim_id=c1["crim_id"],
        charge="robo agravado", sentence_days=730,
        fine=500.0, dictated_by="JUEZ-PENAL",
        created_at="2026-03-01")
    assert conv["status"] == "condenado"
    cert = antecedentes_cert_db(db, "P-ACUS")
    assert cert["convictions"] == 1
    assert cert["chain_verified"] is True
    c2 = open_criminal_case_db(db,
        person_id="P-ACUS", zid="ZID-ACUS",
        created_at="2026-06-01")
    convict_db(db, crim_id=c2["crim_id"],
        charge="receptacion", sentence_days=180,
        dictated_by="JUEZ-PENAL",
        created_at="2026-08-01")
    cert2 = antecedentes_cert_db(db, "P-ACUS")
    assert cert2["convictions"] == 2
    assert cert2["chain_verified"] is True
    db.execute(
        "UPDATE ax_crim_registry SET payload ="
        " 'TAMPER' WHERE person_id = 'P-ACUS' AND"
        " rowid = 1")
    assert antecedentes_verify_db(
        db, "P-ACUS") is False
    db.execute(
        "UPDATE ax_crim_registry SET payload ="
        " 'CONDENA|robo agravado|730' WHERE"
        " person_id = 'P-ACUS' AND rowid = 1")
    assert antecedentes_verify_db(
        db, "P-ACUS") is True
    r1 = reincidence_db(db, "P-ACUS")
    assert r1["level"] == "REINCIDENTE"
    assert reincidence_db(
        db, "P-LIMPIO")["level"] == "PRIMARIO"
    print("OK AX-7: antecedentes hash-chain (tamper detectado y reparado) + reincidencia")


def test_ax8_forense_peritajes_informe(tmp_path) -> None:
    db = SQLiteAdapter(tmp_path / "f.db")
    e8(db)
    with pytest.raises(ValueError):
        open_fx_db(db, kind="ADN")
    with pytest.raises(ValueError):
        open_fx_db(db, kind="TELEPATIA",
            ref_case_id="C1")
    fx = open_fx_db(db, kind="ADN",
        ref_case_id="JC-pen-1",
        created_at="2026-01-01")
    with pytest.raises(ValueError):
        issue_report_db(db, fx["fx_id"],
            conclusion="x", signed_by="PER-1")
    add_finding_db(db, fx_id=fx["fx_id"],
        expert="PER-1", finding="coincidencia 99.9%",
        confidence="alta")
    assert fxs_by_ref_db(db, "JC-pen-1")[0][
        "status"] == "en_proceso"
    rep = issue_report_db(db, fx["fx_id"],
        conclusion="compatibilidad genetica",
        signed_by="PER-1", issued_at="2026-02-01")
    assert rep["report_id"]
    with pytest.raises(ValueError):
        issue_report_db(db, fx["fx_id"],
            conclusion="x", signed_by="PER-1")
    with pytest.raises(ValueError):
        add_finding_db(db, fx_id=fx["fx_id"],
            expert="PER-1", finding="tarde")
    print("OK AX-8: peritaje exige ref + informe que cierra")


def test_ax9_evidencia_custodia(tmp_path) -> None:
    db = SQLiteAdapter(tmp_path / "e.db")
    e9(db)
    with pytest.raises(ValueError):
        ingest_db(db, ref_kind="OTRO", ref_id="C1",
            kind="FISICA", description="cuchillo")
    with pytest.raises(ValueError):
        ingest_db(db, ref_kind="JUSTICIA",
            ref_id="C1", kind="FISICA",
            description="x")
    ev = ingest_db(db, ref_kind="JUSTICIA",
        ref_id="JC-pen-1", kind="FISICA",
        description="cuchillo hallado",
        content_b64="Q1VDSExJTExP",
        actor="POL-1", at="2026-01-01")
    assert len(ev["sha256"]) == 64
    ev2 = ingest_db(db, ref_kind="POLICIA",
        ref_id="INC-1", kind="DIGITAL",
        description="video camara",
        sha256_hex="ab" * 32, actor="POL-1")
    with pytest.raises(ValueError):
        ingest_db(db, ref_kind="JUSTICIA",
            ref_id="C1", kind="FISICA",
            description="x", sha256_hex="corto")
    assert custody_verified_db(db,
                               ev["ev_id"]) is True
    t = transfer_db(db, ev["ev_id"],
        actor="POL-2", to_location="BODEGA-1",
        at="2026-01-02")
    assert t["status"] == "en_custodia"
    a = analyze_db(db, ev["ev_id"],
        actor="PER-1", note="huellas relevantes",
        at="2026-01-03")
    assert a["status"] == "analizada"
    rl0 = release_db(db, ev2["ev_id"],
        actor="POL-1", at="2026-01-04")
    assert rl0["status"] == "liberada"
    with pytest.raises(ValueError):
        analyze_db(db, ev2["ev_id"], actor="X")
    pr = present_db(db, ev["ev_id"],
        actor="FISCAL-1", at="2026-01-10")
    assert pr["status"] == "presentada"
    with pytest.raises(ValueError):
        transfer_db(db, ev["ev_id"], actor="X",
            to_location="Y")
    with pytest.raises(ValueError):
        analyze_db(db, ev["ev_id"], actor="X")
    rl = release_db(db, ev["ev_id"],
        actor="JUEZ-1", at="2026-02-01")
    assert rl["status"] == "liberada"
    with pytest.raises(ValueError):
        analyze_db(db, ev["ev_id"], actor="X")
    chain = custody_of_db(db, ev["ev_id"])
    acts = [c["action"] for c in chain]
    assert acts == ["INGRESO", "TRANSFERENCIA",
                    "ANALISIS", "PRESENTACION",
                    "LIBERACION"]
    assert custody_verified_db(db,
                               ev["ev_id"]) is True
    print("OK AX-9: sha256 + custodia con transiciones validadas + liberada terminal")
