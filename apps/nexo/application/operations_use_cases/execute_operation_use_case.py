
from __future__ import annotations
from apps.nexo.domain.operations.operations_engine import (
    OperationsEngine)
from apps.nexo.domain.operations.operations_validation_engine import (
    OperationsValidationEngine)
from apps.nexo.domain.operations.process_tracking_engine import (
    ProcessTrackingEngine)

class ExecuteOperationUseCase:
    """Valida, aprueba y ejecuta una operacion dejando
    trazabilidad completa. La operacion debe estar en
    PENDING. Si la validacion falla -> REJECTED."""

    def __init__(self, operations, validations,
                 tracking):
        self._ops = operations
        self._val = validations
        self._track = tracking

    def execute(self, *, operation_id, amount,
                description, actor) -> dict:
        op = self._ops.get_operation(operation_id)
        if not op:
            return {"operation_id": operation_id,
                    "executed": False,
                    "reason": "not_found"}
        if op["status"] != "PENDING":
            return {"operation_id": operation_id,
                    "executed": False,
                    "reason": "estado="
                              + op["status"]}
        v = self._val.validate_operation(
            operation_id=operation_id,
            amount=amount, description=description)
        if not v["valid"]:
            self._ops.transition(
                operation_id=operation_id,
                new_status="REJECTED", actor=actor)
            self._track.append_event(
                process_id=operation_id,
                event_type="REJECTED", actor=actor,
                detail="validacion fallo")
            return {"operation_id": operation_id,
                    "executed": False,
                    "reason": "validacion",
                    "validations": v}
        self._ops.transition(operation_id=operation_id,
                             new_status="VALIDATED",
                             actor=actor)
        self._ops.transition(operation_id=operation_id,
                             new_status="APPROVED",
                             actor=actor)
        self._ops.transition(operation_id=operation_id,
                             new_status="IN_PROGRESS",
                             actor=actor)
        final = self._ops.transition(
            operation_id=operation_id,
            new_status="COMPLETED", actor=actor)
        self._track.append_event(
            process_id=operation_id,
            event_type="COMPLETED", actor=actor,
            detail="operacion ejecutada")
        return {"operation_id": operation_id,
                "executed": True,
                "status": final["status"],
                "operation_number":
                    final["operation_number"]}
