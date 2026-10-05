
from __future__ import annotations
from apps.nexo.domain.executive.executive_alert_engine import ExecutiveAlertEngine

class GenerateAlertsUseCase:
    def __init__(self, alert_engine):
        self._engine = alert_engine

    def execute(self, *, level, title, description,
                source_module=None, reference_id=None, metadata=None):
        return self._engine.create_alert(
            level=level, title=title, description=description,
            source_module=source_module, reference_id=reference_id,
            metadata=metadata)
