import pytest
from shared_engines.common.clocks import FrozenClock
from shared_engines.storage.database import SQLiteAdapter
from apps.nexo.domain.meta_government.national_intelligence_engine import (
    NationalIntelligenceEngine)


def _env(tmp_path):
    db = SQLiteAdapter(tmp_path / "g.db")
    return db, NationalIntelligenceEngine(db,
                                          FrozenClock())


def test_capa_a_indicadores_vivos(tmp_path) -> None:
    db, gov = _env(tmp_path)
    with pytest.raises(ValueError):
        gov.report_indicator(app=" ", indicator="x",
                             value=1)
    with pytest.raises(ValueError):
        gov.report_indicator(app="semilla",
            indicator="x", value=-1)
    with pytest.raises(ValueError):
        gov.report_indicator(app="semilla",
            indicator="x", value=1,
            severity="URGENTE")
    i1 = gov.report_indicator(app="semilla",
        module="matricula", indicator="matriculados",
        value=1250000, unit="alumnos",
        territory="SAN_SALVADOR", trend="subiendo",
        event_id="SEMILLA_1")
    assert i1["capa"] == "A"
    gov.report_indicator(app="agro",
        indicator="sequia_zona_norte", value=1,
        severity="CRITICA", trend="subiendo")
    assert len(gov.indicators_of("agro")) == 1
    gov.deactivate_indicator(i1["ind_id"])
    assert len(gov.indicators_of("semilla")) == 0
    print("OK Capa A: indicadores vivos con severidad/tendencia/territorio + desactivacion")


def test_capa_b_alertas_con_recomendacion(tmp_path) -> None:
    db, gov = _env(tmp_path)
    with pytest.raises(ValueError):
        gov.raise_national_alert(domain="alimentacion",
            indicator="produccion_maiz",
            current_value=82.0,
            impact="deficit en 90 dias",
            recommendation=" ")
    a = gov.raise_national_alert(domain="alimentacion",
        indicator="produccion_maiz",
        current_value=82.0,
        impact="deficit alimentario en 90 dias",
        recommendation="activar produccion alternativa"
                       " e importar 50k ton",
        responsible="Ministerio de Agricultura",
        severity="CRITICA")
    assert a["capa"] == "B"
    assert len(gov.active_alerts_db()) == 1
    r = gov.resolve_national_alert(a["alert_id"],
        note="produccion recuperada 12%")
    assert r["status"] == "resuelta"
    with pytest.raises(ValueError):
        gov.resolve_national_alert(a["alert_id"])
    assert gov.active_alerts_db() == []
    print("OK Capa B: IMPACTO+RECOMENDACION+RESPONSABLE (regla 66) + resolucion unica")


def test_capa_c_cadena_causal(tmp_path) -> None:
    db, gov = _env(tmp_path)
    e1 = gov.chain_event(source_app="agro",
        event_type="SEQUIA_DETECTADA",
        ref="ZONA-NORTE",
        detail="deficit hidrico 40 dias",
        severity="ALTA")
    e2 = gov.chain_event(source_app="agro",
        event_type="PRODUCCION_MAIZ_REDUCIDA",
        ref="ZONA-NORTE", detail="-18%",
        prev_event=e1["ev_id"])
    e3 = gov.chain_event(source_app="subastas",
        event_type="DEMANDA_MAIZ_AUMENTA",
        ref="MAIZ", prev_event=e2["ev_id"])
    e4 = gov.chain_event(source_app="nexo",
        event_type="PRECIO_MAIZ_AUMENTA",
        ref="MAIZ", prev_event=e3["ev_id"])
    e5 = gov.chain_event(source_app="axis",
        event_type="RIESGO_NUTRICIONAL_AUMENTA",
        ref="ZONA-NORTE", prev_event=e4["ev_id"],
        severity="CRITICA")
    with pytest.raises(LookupError):
        gov.chain_event(source_app="agro",
            event_type="X",
            prev_event="NO-EXISTE")
    ch = gov.causal_chain(e5["ev_id"])
    assert ch["length"] == 5
    types = [c["event_type"] for c in ch["chain"]]
    assert types[0] == "SEQUIA_DETECTADA"
    assert types[-1] == "RIESGO_NUTRICIONAL_AUMENTA"
    print("OK Capa C: cadena causal cross-app recorrible")


def test_alarmas_amber_sismo_crisis(tmp_path) -> None:
    db, gov = _env(tmp_path)
    with pytest.raises(ValueError):
        gov.raise_alarm(kind="ZYRA_AMBER",
            subject="menor desaparecido")
    with pytest.raises(ValueError):
        gov.raise_alarm(kind="TERROR", subject="x")
    am = gov.raise_alarm(kind="ZYRA_AMBER",
        zone="ZONA-5", target="ZID-NENE-1",
        subject="menor desaparecido ZID-NENE-1",
        body="alerta a telefonos de la zona")
    assert am["kind"] == "ZYRA_AMBER"
    si = gov.raise_alarm(kind="SISMO",
        zone="NACIONAL", subject="sismo 6.2 costa")
    assert len(gov.alarms_active_db()) == 2
    assert len(gov.alarms_active_db(
        kind="ZYRA_AMBER")) == 1
    c = gov.clear_alarm(si["alarm_id"])
    assert c["status"] == "despejada"
    with pytest.raises(ValueError):
        gov.clear_alarm(si["alarm_id"])
    snap = gov.national_snapshot()
    assert "capa_b_alertas" in snap
    assert "apps" in snap
    print("OK ALARMAS: ZYRA_AMBER exige ZID del menor (regla 78) + SISMO + despeje unico + snapshot nacional")
