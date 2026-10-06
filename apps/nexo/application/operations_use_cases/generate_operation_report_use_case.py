
from __future__ import annotations
from apps.nexo.domain.operations.operations_engine import (
    OperationsEngine)
from apps.nexo.domain.operations.process_tracking_engine import (
    ProcessTrackingEngine)

class GenerateOperationReportUseCase:
    """Reporte formal de operacion con timeline
    completo y totales de empresa (auditable para
    gobiernos y bancos)."""

    def __init__(self, operations, tracking):
        self._ops = operations
        self._track = tracking

    def execute(self, *, operation_id) -> dict:
        op = self._ops.get_operation(operation_id)
        if not op:
            return {"operation_id": operation_id,
                    "found": False}
        return {"report_type": "OPERATION_REPORT",
                "operation": op,
                "timeline":
                    self._track.get_timeline(
                        operation_id),
                "company_totals":
                    self._ops.company_totals(
                        op["company_id"])}
