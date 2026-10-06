
from __future__ import annotations
from apps.nexo.domain.operations.operations_engine import (
    OperationsEngine)
from apps.nexo.domain.operations.process_tracking_engine import (
    ProcessTrackingEngine)
from apps.nexo.domain.operations.operational_control_engine import (
    OperationalControlEngine)

class MonitorOperationUseCase:
    """Estado + timeline + controles de una operacion
    (repara el monitor_operation inexistente del
    viejo)."""

    def __init__(self, operations, tracking, controls):
        self._ops = operations
        self._track = tracking
        self._ctrl = controls

    def execute(self, *, operation_id) -> dict:
        op = self._ops.get_operation(operation_id)
        if not op:
            return {"operation_id": operation_id,
                    "found": False}
        return {"operation_id": operation_id,
                "found": True,
                "operation": op,
                "timeline":
                    self._track.get_timeline(
                        operation_id),
                "controls":
                    self._ctrl.controls_of(
                        operation_id),
                "all_controls_passed":
                    self._ctrl.all_passed(
                        operation_id)}
