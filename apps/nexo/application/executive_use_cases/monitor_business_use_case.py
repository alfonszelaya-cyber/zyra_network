
from __future__ import annotations
from apps.nexo.domain.executive.executive_monitor_engine import ExecutiveMonitorEngine

class MonitorBusinessUseCase:
    def __init__(self, monitor_engine):
        self._engine = monitor_engine

    def execute(self, *, indicators):
        monitoring = self._engine.monitor_business(indicators=indicators)
        anomalies = self._engine.detect_anomalies(indicators=indicators)
        return {"monitoring": monitoring, "anomalies": anomalies,
                "status": "MONITORED"}
