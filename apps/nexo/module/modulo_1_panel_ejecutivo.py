
"""Modulo 1 Panel Ejecutivo - orquestador."""
from __future__ import annotations
from typing import Dict
from apps.nexo.domain.executive.executive_dashboard_engine import (
    ExecutiveDashboardEngine)
from apps.nexo.domain.executive.executive_alert_engine import (
    ExecutiveAlertEngine)
from apps.nexo.domain.executive.executive_decision_engine import (
    ExecutiveDecisionEngine)
from apps.nexo.domain.executive.executive_kpi_engine import (
    ExecutiveKPIEngine)
from apps.nexo.domain.executive.executive_metrics_engine import (
    ExecutiveMetricsEngine)
from apps.nexo.domain.executive.executive_monitor_engine import (
    ExecutiveMonitorEngine)
from apps.nexo.domain.executive.executive_report_engine import (
    ExecutiveReportEngine)

class Modulo1PanelEjecutivo:
    """Panel Ejecutivo: orquesta los 7 engines."""

    def __init__(self):
        self.dashboard = ExecutiveDashboardEngine()
        self.alerts = ExecutiveAlertEngine()
        self.decisions = ExecutiveDecisionEngine()
        self.kpis = ExecutiveKPIEngine()
        self.metrics = ExecutiveMetricsEngine()
        self.monitor = ExecutiveMonitorEngine()
        self.reports = ExecutiveReportEngine()

    def resumen_general(self):
        kpis = self.kpis.get_last_kpis() or {}
        alerts = self.alerts.get_open_alerts()
        decisions = self.decisions.get_decisions()
        return self.dashboard.build_dashboard(
            kpis=kpis, metrics={}, alerts=alerts,
            decisions=decisions)

    def crear_alerta(self, *, level, title, description,
                     source_module=None):
        return self.alerts.create_alert(
            level=level, title=title,
            description=description,
            source_module=source_module)

    def crear_decision(self, *, context,
                       recommendation="REVIEW_REQUIRED",
                       priority="NORMAL"):
        return self.decisions.support_decision(
            decision_context=context,
            recommendation=recommendation,
            priority=priority)

    def calcular_kpis(self, *, metrics):
        k = self.kpis.generate_kpis(metrics=metrics)
        score = self.kpis.calculate_executive_score(kpis=k)
        return {"kpis": k, "executive_score": score}

    def monitorear(self, *, indicators):
        m = self.monitor.monitor_business(indicators=indicators)
        anomalies = self.monitor.detect_anomalies(indicators=indicators)
        for a in anomalies:
            if a["value"] > 500:
                self.alerts.create_alert(
                    level="HIGH",
                    title="Anomalia: " + a["indicator"],
                    description="Valor " + str(a["value"]),
                    source_module="modulo_1")
        return {"monitoring": m, "anomalies": anomalies}

    def generar_reporte(self):
        dashboard = self.resumen_general()
        return self.reports.generate_report(
            dashboard_data=dashboard, report_scope="NEXO")

    def auditoria_integral(self):
        return {"auditoria": "INTEGRAL_ZYRA",
                "alertas": self.alerts.generate_summary(),
                "decisiones": self.decisions.generate_summary(),
                "monitoreo": self.monitor.generate_summary()}
