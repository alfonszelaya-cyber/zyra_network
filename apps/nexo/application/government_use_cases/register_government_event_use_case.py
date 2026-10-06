
from __future__ import annotations

class RegisterGovernmentEventUseCase:
    """Registra evento institucional con validacion."""

    def __init__(self, validation, registry=None,
                 compliance=None):
        self._val = validation
        self._reg = registry
        self._comp = compliance

    def execute(self, *, institution_id, period,
                budgeted="0", event="",
                actor="") -> dict:
        v = self._val.validate_program(
            subject=event or "gov_event",
            budgeted=budgeted,
            institution_id=institution_id,
            period=period)
        program = None
        if v["valid"] and self._reg is not None:
            program = self._reg.create_program(
                institution_id=institution_id,
                name=event or "programa",
                period=period,
                budgeted=budgeted)
        return {"valid": v["valid"],
                "program": program}
