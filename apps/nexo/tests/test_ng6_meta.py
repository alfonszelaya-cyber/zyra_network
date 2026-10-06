import pytest
from shared_engines.common.clocks import FrozenClock
from shared_engines.storage.database import SQLiteAdapter
from apps.nexo.domain.meta_government.policy_engine import PolicyEngine
from apps.nexo.domain.meta_government.national_strategy_engine import NationalStrategyEngine
from apps.nexo.domain.meta_government.public_metrics_engine import PublicMetricsEngine
from apps.nexo.domain.meta_government.institutional_coordination_engine import InstitutionalCoordinationEngine
from apps.nexo.domain.meta_government.decision_coordination_engine import DecisionCoordinationEngine
from apps.nexo.domain.meta_government.governance_analytics_engine import GovernanceAnalyticsEngine
from apps.nexo.domain.meta_government.national_dashboard_engine import NationalDashboardEngine
from apps.nexo.domain.government.government_registry import GovernmentRegistry
from apps.nexo.domain.government.government_compliance_engine import GovernmentComplianceEngine
from apps.nexo.application.meta_government_use_cases.create_policy_use_case import CreatePolicyUseCase
from apps.nexo.application.meta_government_use_cases.generate_national_dashboard_use_case import GenerateNationalDashboardUseCase
from apps.nexo.application.meta_government_use_cases.support_public_decision_use_case import SupportPublicDecisionUseCase
from apps.nexo.application.meta_government_use_cases.coordinate_institutions_use_case import CoordinateInstitutionsUseCase
from apps.nexo.application.meta_government_use_cases.coordinate_strategy_use_case import CoordinateStrategyUseCase
from apps.nexo.application.meta_government_use_cases.analyze_governance_use_case import AnalyzeGovernanceUseCase

def test_politicas_estrategia(tmp_path) -> None:
    db = SQLiteAdapter(tmp_path / "mg1.db")
    clock = FrozenClock()
    pol = PolicyEngine(db, clock)
    uc = CreatePolicyUseCase(pol)
    p = uc.execute(title="Gobierno Digital",
        scope="NATIONAL", activate=True)
    assert p["status"] == "ACTIVE"
    assert (uc.execute(
        title="Politica en borrador"
        )["status"] == "DRAFT")
    strat = NationalStrategyEngine(db, clock)
    ucs = CoordinateStrategyUseCase(strat)
    o = ucs.execute(title="Digitalizar 100 tramites",
        target_period="2027",
        progress_pct=40)
    assert o["progress_pct"] == 40.0
    with pytest.raises(ValueError):
        strat.update_progress(
            objective_id=o["objective_id"],
            progress_pct=150)
    print("OK politicas+estrategia: ciclo de vida y avance")

def test_metricas_acuerdos_decisiones(tmp_path) -> None:
    db = SQLiteAdapter(tmp_path / "mg2.db")
    clock = FrozenClock()
    met = PublicMetricsEngine(db, clock)
    met.publish_metric(name="escuelas_conectadas",
        period="2026-03", value="1200",
        unit="escuelas")
    met.publish_metric(name="escuelas_conectadas",
        period="2026-04", value="1350",
        unit="escuelas")
    latest = met.latest("escuelas_conectadas")
    assert latest["value"] == "1350"
    coord = InstitutionalCoordinationEngine(db, clock)
    ucc = CoordinateInstitutionsUseCase(coord)
    a = ucc.execute(
        institutions=["GOV-MH", "GOV-MAG"],
        subject="Interop agro-fiscal",
        activate=True)
    assert a["status"] == "ACTIVE"
    assert len(coord.active_agreements()) == 1
    dec = DecisionCoordinationEngine(db, clock)
    ucd = SupportPublicDecisionUseCase(dec)
    d = ucd.execute(
        title="Mejor ruta para programa",
        options=["A", "B", "C"],
        analysis="B menor costo y menor riesgo",
        chosen="B")
    assert d["status"] == "DECIDED"
    assert d["chosen"] == "B"
    with pytest.raises(ValueError):
        dec.decide(decision_id=d["decision_id"],
            chosen="A")
    with pytest.raises(ValueError):
        ucd.execute(title="x", options=["A"],
                    chosen="Z")
    print("OK metricas+acuerdos+decisiones (nivel 5 coordinacion)")

def test_dashboard_nacional_analitica(tmp_path) -> None:
    db = SQLiteAdapter(tmp_path / "mg3.db")
    clock = FrozenClock()
    reg = GovernmentRegistry(db, clock)
    comp = GovernmentComplianceEngine(db, clock)
    i1 = reg.create_institution(name="Ministerio A",
        kind="MINISTRY")
    i2 = reg.create_institution(name="Municipio B",
        kind="MUNICIPALITY")
    reg.create_program(
        institution_id=i1["institution_id"],
        name="P1", period="2026-03",
        budgeted="100000")
    p2 = reg.create_program(
        institution_id=i2["institution_id"],
        name="P2", period="2026-03",
        budgeted="50000")
    reg.commit_funds(
        program_id=p2["program_id"],
        amount="25000")
    reg.accrue(program_id=p2["program_id"],
        amount="20000")
    reg.pay(program_id=p2["program_id"],
        amount="10000")
    comp.register_requirement(
        institution_id=i1["institution_id"],
        requirement="req1")
    met = PublicMetricsEngine(db, clock)
    dash = NationalDashboardEngine(db, clock,
        registry=reg, metrics=met)
    snap = GenerateNationalDashboardUseCase(
        dash).execute(period="2026-03")
    assert snap["institutions"] == 2
    assert snap["programs"] == 2
    assert snap["total_budgeted"] == "150000.00"
    assert (snap["national_execution_pct"]
            == 6.67)
    latest = met.latest("national_execution_pct")
    assert latest["value"] == "6.67"
    an = GovernanceAnalyticsEngine(db, clock,
        registry=reg, compliance=comp)
    r = AnalyzeGovernanceUseCase(an).execute(
        period="2026-03")
    assert r["programs"] == 2
    assert (r["national_execution_pct"]
            == 6.67)
    assert len(r["by_institution"]) == 2
    print("OK dashboard nacional + analitica: agregados con Decimal")
