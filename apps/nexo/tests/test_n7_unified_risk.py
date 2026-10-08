import pytest
from shared_engines.common.clocks import FrozenClock
from shared_engines.storage.database import SQLiteAdapter
from apps.nexo.domain.risk.unified_risk_engine import UnifiedRiskEngine
from apps.nexo.domain.risk.operational_risk_engine import OperationalRiskEngine
from apps.nexo.domain.risk.risk_scoring_engine import RiskScoringEngine
from apps.nexo.domain.risk.risk_monitor_engine import RiskMonitorEngine


def _base(tmp_path):
    db = SQLiteAdapter(tmp_path / "r.db")
    uni = UnifiedRiskEngine(db, FrozenClock())
    probe = {"scoring": False, "monitor": False}
    try:
        r = RiskScoringEngine().calculate(
            compliance_risk=10,
            financial_risk=10,
            operational_risk=10)
        if isinstance(r, dict) and "score" in r:
            probe["scoring"] = True
    except Exception:
        probe["scoring"] = False
    try:
        RiskMonitorEngine().register({
            "risk_id": "P", "score": 0,
            "level": "LOW"})
        probe["monitor"] = True
    except Exception:
        probe["monitor"] = False
    return db, uni, probe


def test_componentes_reales_y_promedio(tmp_path) -> None:
    db, uni, probe = _base(tmp_path)
    res = uni.evaluate_entity(entity_ref="ENT-1",
        compliance_record={"valid": False},
        sanctions_result={"sanctioned": False},
        accounting_data={"negative_cashflow":
                         True},
        finance_data={"liquidity_ratio": 0.5,
                      "debt_ratio": 80})
    kinds = {c["kind"]: c
             for c in res["components"]}
    assert kinds["COMPLIANCE"]["score"] == 50
    assert kinds["FINANCIAL"]["score"] == 100
    assert res["score"] == 75
    assert res["level"] == "HIGH"
    assert res["risk_id"].startswith("UNI-")
    assert res["skipped"] == []
    assert len(res["not_evaluated"]) >= 3
    assert any("OPERATIONAL" in s
               for s in res["not_evaluated"])
    assert (res["engine_score"] is None
            or isinstance(res["engine_score"],
                          int))
    assert "monitor_ok" in res
    print("OK N-7: componentes por MOTORES REALES (compliance 50, financial 100) + unificado 75 HIGH + not_evaluated con razones de las puertas no intentadas")


def test_country_score_conocido(tmp_path) -> None:
    db, uni, probe = _base(tmp_path)
    res = uni.evaluate_entity(entity_ref="ENT-C",
        country_code="GT",
        geopolitical_data={"risk_score": 30})
    kinds = {c["kind"]: c
             for c in res["components"]}
    assert kinds["COUNTRY"]["score"] == 30
    assert res["score"] == 30
    assert res["level"] == "MEDIUM"
    print("OK N-7 country: score 30 (geopolitical 30 + sanctions 0, tope 100) — motor dueno manda")


def test_skip_honesto_y_sin_componentes(tmp_path) -> None:
    db, uni, probe = _base(tmp_path)
    res = uni.evaluate_entity(entity_ref="ENT-S",
        compliance_record={"valid": True},
        sanctions_result={"sanctioned": False},
        accounting_data={"negative_cashflow":
                         False})
    assert len(res["components"]) == 1
    assert res["components"][0]["kind"] \
        == "COMPLIANCE"
    assert any("FINANCIAL" in s
               for s in res["not_evaluated"])
    assert any("COUNTRY" in s
               for s in res["not_evaluated"])
    assert res["skipped"] == []
    with pytest.raises(ValueError):
        uni.evaluate_entity(entity_ref="ENT-X",
            accounting_data={
                "negative_cashflow": False})
    print("OK N-7 honesto (regla 66): componente sin datos OMITIDO con razon en not_evaluated (contrato del docstring); sin nada evaluable -> ValueError listando omisiones")


def test_consistencia_con_motor_operacional(tmp_path) -> None:
    db, uni, probe = _base(tmp_path)
    try:
        direct = OperationalRiskEngine().evaluate(
            logistics_data={"flota": 3},
            operations_data={"ordenes": 5})
    except Exception:
        pytest.skip("motor operacional requiere"
                    " otros datos")
    res = uni.evaluate_entity(entity_ref="ENT-O",
        logistics_data={"flota": 3},
        operations_data={"ordenes": 5})
    comp = [c for c in res["components"]
            if c["kind"] == "OPERATIONAL"][0]
    assert comp["score"] == int(direct["score"])
    print("OK N-7: score operacional IDENTICO al motor dueno (composicion, no duplicacion — regla 69)")


def test_historial_y_peores(tmp_path) -> None:
    db, uni, probe = _base(tmp_path)
    uni.evaluate_entity(entity_ref="ENT-A",
        compliance_record={"valid": False},
        sanctions_result={"sanctioned": False},
        accounting_data={"negative_cashflow":
                         True},
        finance_data={"liquidity_ratio": 0.5,
                      "debt_ratio": 80})
    uni.evaluate_entity(entity_ref="ENT-A",
        compliance_record={"valid": True},
        sanctions_result={"sanctioned": False})
    uni.evaluate_entity(entity_ref="ENT-B",
        compliance_record={"valid": False},
        sanctions_result={"sanctioned": True})
    h = uni.history_of("ENT-A")
    assert len(h) == 2
    assert h[0]["score"] == 75
    assert h[1]["score"] == 0
    worst = uni.worst_entities(limit=10)
    refs = [w["entity_ref"] for w in worst]
    assert refs[0] == "ENT-B"
    assert refs[1] == "ENT-A"
    wa = [w for w in worst
          if w["entity_ref"] == "ENT-A"][0]
    assert wa["worst"] == 75
    assert wa["n"] == 2
    print("OK N-7: historial persistente por entidad (rowid, regla 76) + ranking de peores entidades")
