
"""Tests L4: executive + bunker."""
from __future__ import annotations
from apps.nexo.domain.executive.executive_alert_engine import (
    ExecutiveAlertEngine)
from apps.nexo.domain.executive.executive_kpi_engine import (
    ExecutiveKPIEngine)
from apps.nexo.domain.executive.executive_monitor_engine import (
    ExecutiveMonitorEngine)
from apps.nexo.module.modulo_1_panel_ejecutivo import (
    Modulo1PanelEjecutivo)
from apps.nexo.module.modulo_001_super_bunker import (
    emit, get_bunker_events)
from apps.nexo.application.executive_use_cases.generate_alerts_use_case import (
    GenerateAlertsUseCase)
from apps.nexo.application.executive_use_cases.generate_kpi_use_case import (
    GenerateKPIUseCase)

def test_alert_engine() -> None:
    eng = ExecutiveAlertEngine()
    a = eng.create_alert(level="HIGH", title="Test",
                         description="Descripcion")
    assert a["status"] == "OPEN"
    assert len(eng.get_critical_alerts()) == 0
    e = eng.escalate_alert(a["alert_id"])
    assert e["status"] == "ESCALATED"
    print("OK exec: alertas crear/escalar")

def test_kpi_score() -> None:
    eng = ExecutiveKPIEngine()
    k = eng.generate_kpis(metrics={
        "revenue_growth": 15, "profit_margin": 20,
        "cash_flow": 10, "customer_growth": 5})
    score = eng.calculate_executive_score(kpis=k)
    assert score == 12.5
    print("OK exec: KPI score 12.5")

def test_monitor_anomalies() -> None:
    eng = ExecutiveMonitorEngine()
    eng.monitor_business(indicators={"ventas": 50, "gastos": 200})
    anomalies = eng.detect_anomalies(
        indicators={"ventas": 50, "gastos": 200})
    assert len(anomalies) == 1
    assert anomalies[0]["indicator"] == "gastos"
    print("OK exec: anomalias")

def test_panel_ejecutivo() -> None:
    panel = Modulo1PanelEjecutivo()
    k = panel.calcular_kpis(metrics={
        "revenue_growth": 10, "profit_margin": 15,
        "cash_flow": 8, "customer_growth": 3})
    assert k["executive_score"] == 9.0
    panel.crear_alerta(level="HIGH", title="Alerta",
                       description="Test")
    r = panel.generar_reporte()
    assert r["report_type"] == "EXECUTIVE"
    a = panel.auditoria_integral()
    assert a["auditoria"] == "INTEGRAL_ZYRA"
    print("OK exec: panel integral")

def test_bunker_emit() -> None:
    emit("TEST_EVENT")
    events = get_bunker_events()
    assert events[-1]["event"] == "TEST_EVENT"
    print("OK bunker: emit + get_bunker_events")
