
from __future__ import annotations
from apps.nexo.domain.compliance.sanctions_monitor import SanctionsMonitor

class MonitorSanctionsUseCase:
    def __init__(self, sanctions_monitor):
        self._engine = sanctions_monitor

    def execute(self, *, company_id, entity_name=""):
        v = self._engine.verify(entity_name=entity_name or company_id)
        matches = [v] if v["sanctioned"] else []
        return {"company_id": company_id, "matches_found": len(matches),
                "matches": matches,
                "status": "INFORMATIONAL" if matches else "CLEAR"}
