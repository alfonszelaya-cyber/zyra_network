
from __future__ import annotations
from apps.nexo.domain.operations.operations_validation_engine import (
    OperationsValidationEngine)
from apps.nexo.domain.operations.operational_control_engine import (
    OperationalControlEngine)

class ValidateOperationUseCase:
    """Valida operacion + corre controles de limite de
    monto y duplicado. Todo queda registrado."""

    def __init__(self, validations, controls):
        self._val = validations
        self._ctrl = controls

    def execute(self, *, operation_id, amount,
                description, amount_limit,
                fingerprint="",
                previous_fingerprints=None) -> dict:
        v = self._val.validate_operation(
            operation_id=operation_id,
            amount=amount, description=description)
        c1 = self._ctrl.register_control(
            operation_id=operation_id,
            control_type="AMOUNT_LIMIT")
        r1 = self._ctrl.check_amount_limit(
            control_id=c1["control_id"],
            amount=amount, limit=amount_limit)
        c2 = self._ctrl.register_control(
            operation_id=operation_id,
            control_type="DUPLICATE")
        r2 = self._ctrl.check_duplicate(
            control_id=c2["control_id"],
            fingerprint=fingerprint,
            previous_fingerprints=
            previous_fingerprints)
        ok = (v["valid"] and r1["passed"]
              and r2["passed"])
        return {"operation_id": operation_id,
                "valid": ok,
                "validation": v,
                "amount_limit": r1,
                "duplicate_check": r2}
