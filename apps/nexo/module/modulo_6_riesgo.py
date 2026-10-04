
"""Modulo 6 Riesgo - orquestador."""
from __future__ import annotations
from typing import Dict
from apps.nexo.domain.risk.financial_risk_engine import FinancialRiskEngine
from apps.nexo.domain.risk.operational_risk_engine import OperationalRiskEngine
from apps.nexo.domain.risk.compliance_risk_engine import ComplianceRiskEngine
from apps.nexo.domain.risk.risk_engine import RiskEngine
from apps.nexo.domain.risk.risk_monitor_engine import RiskMonitorEngine

class Modulo6Riesgo:
    def __init__(self, *, financial=None, operational=None, compliance=None,
                 master=None, monitor=None):
        self.financial = financial or FinancialRiskEngine()
        self.operational = operational or OperationalRiskEngine()
        self.compliance = compliance or ComplianceRiskEngine()
        self.master = master or RiskEngine()
        self.monitor = monitor or RiskMonitorEngine()

    def evaluar_financiero(self, *, accounting_data, finance_data):
        r = self.financial.evaluate(accounting_data=accounting_data, finance_data=finance_data)
        self.monitor.register(r)
        return r

    def evaluar_operativo(self, *, logistics_data, operations_data):
        r = self.operational.evaluate(logistics_data=logistics_data, operations_data=operations_data)
        self.monitor.register(r)
        return r

    def evaluar_legal(self, *, compliance_record, sanctions_result):
        r = self.compliance.evaluate(compliance_record=compliance_record, sanctions_result=sanctions_result)
        self.monitor.register(r)
        return r

    def evaluar_integral(self, *, accounting_data, finance_data, logistics_data,
                         operations_data, compliance_record, sanctions_result):
        fin = self.financial.evaluate(accounting_data=accounting_data, finance_data=finance_data)
        opr = self.operational.evaluate(logistics_data=logistics_data, operations_data=operations_data)
        cmp = self.compliance.evaluate(compliance_record=compliance_record, sanctions_result=sanctions_result)
        r = self.master.evaluate(risk_components={"FINANCIAL": fin, "OPERATIONAL": opr, "COMPLIANCE": cmp})
        self.monitor.register(r)
        return r

    def alertas_activas(self):
        return self.monitor.get_active_alerts()
