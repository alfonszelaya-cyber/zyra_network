
"""Tests L3: compliance + risk."""
from __future__ import annotations
from shared_engines.common.clocks import FrozenClock
from shared_engines.storage.database import SQLiteAdapter
from apps.nexo.domain.compliance.compliance_engine import ComplianceEngine
from apps.nexo.domain.compliance.sanctions_monitor import SanctionsMonitor
from apps.nexo.domain.risk.risk_scoring_engine import RiskScoringEngine
from apps.nexo.domain.risk.fraud_detection_engine import FraudDetectionEngine
from apps.nexo.domain.risk.risk_evaluation_engine import RiskEvaluationEngine
from apps.nexo.module.modulo_6_riesgo import Modulo6Riesgo
from apps.nexo.application.compliance_use_cases.monitor_sanctions_use_case import MonitorSanctionsUseCase
from apps.nexo.application.risk_use_cases.calculate_risk_score_use_case import CalculateRiskScoreUseCase
from apps.nexo.application.risk_use_cases.evaluate_risk_use_case import EvaluateRiskUseCase

def _db(tmp_path):
    return SQLiteAdapter(tmp_path / "rc.db")

def test_compliance_engine(tmp_path) -> None:
    eng = ComplianceEngine(_db(tmp_path), FrozenClock())
    eng.register_event(event_type="REVIEW", entity_id="E1", details={"a": 1})
    v = eng.register_violation(entity_id="E1", violation_type="LATE_FILING", details={})
    assert v["status"] == "OPEN"
    s = eng.generate_summary()
    assert s["events"] == 1 and s["violations"] == 1
    print("OK: compliance engine")

def test_sanctions_informa(tmp_path) -> None:
    mon = SanctionsMonitor(_db(tmp_path), FrozenClock(), sanctioned_names=["MALO S.A."])
    assert mon.verify(entity_name="MALO S.A.")["sanctioned"] is True
    assert mon.verify(entity_name="BUENO S.A.")["sanctioned"] is False
    r = MonitorSanctionsUseCase(mon).execute(company_id="C1", entity_name="MALO S.A.")
    assert r["status"] == "INFORMATIONAL"
    assert mon.generate_summary()["sanctioned_entities"] == 1
    print("OK: sanciones informa no bloquea")

def test_risk_scoring(tmp_path) -> None:
    z = {"score": 0}
    r = RiskScoringEngine().calculate(
        compliance_risk=z, financial_risk={"score": 80}, operational_risk=z,
        geopolitical_risk=z, fraud_risk=z, supply_chain_risk=z,
        sanctions_risk=z, war_risk=z)
    assert r["global_score"] == 10.0 and r["risk_level"] == "LOW"
    print("OK: scoring")

def test_fraud(tmp_path) -> None:
    r = FraudDetectionEngine().detect(
        client_data={"client_id": "C1"},
        accounting_data={"duplicate_transactions": 2, "unusual_amounts": True},
        operations_data={"abnormal_activity": True})
    assert r["level"] == "CRITICAL" and "ABNORMAL_ACTIVITY" in r["flags"]
    print("OK: fraude")

def test_modulo6(tmp_path) -> None:
    m6 = Modulo6Riesgo()
    r = m6.evaluar_integral(
        accounting_data={}, finance_data={"liquidity_ratio": 0.5},
        logistics_data={"delayed_shipments": 5}, operations_data={"incidents": 1},
        compliance_record={"valid": False}, sanctions_result={"sanctioned": False})
    assert r["score"] > 0 and r["level"] == "MEDIUM"
    assert m6.alertas_activas() == []
    critico = m6.evaluar_legal(compliance_record={"valid": False},
                               sanctions_result={"sanctioned": True})
    assert critico["level"] in ("HIGH", "CRITICAL")
    assert m6.alertas_activas()
    print("OK: modulo 6 - MEDIUM sin alerta, CRITICAL con alerta")

def test_use_cases(tmp_path) -> None:
    r1 = CalculateRiskScoreUseCase(RiskScoringEngine()).execute(
        entity_data={"financial_risk": {"score": 80}})
    assert r1["risk_score"] == 10.0
    r2 = EvaluateRiskUseCase(RiskEvaluationEngine()).execute(
        risk_context={"components": {"A": {"score": 90}}})
    assert r2["evaluation"]["level"] == "CRITICAL"
    print("OK: use cases")
