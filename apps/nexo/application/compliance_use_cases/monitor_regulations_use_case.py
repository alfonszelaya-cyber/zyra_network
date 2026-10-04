
from __future__ import annotations
from apps.nexo.domain.compliance.regulatory_monitor import RegulatoryMonitor

class MonitorRegulationsUseCase:
    def __init__(self, regulatory_monitor):
        self._engine = regulatory_monitor

    def execute(self, *, jurisdiction):
        check = self._engine.monitor(jurisdiction=jurisdiction)
        alerts = self._engine.get_alerts_by_jurisdiction(jurisdiction)
        return {"jurisdiction": jurisdiction, "check_id": check["check_id"],
                "regulations_found": len(alerts), "regulations": alerts}
