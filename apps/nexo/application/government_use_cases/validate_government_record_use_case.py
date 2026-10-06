
from __future__ import annotations

class ValidateGovernmentRecordUseCase:
    """Validacion pura de registro gubernamental."""

    def __init__(self, validation):
        self._val = validation

    def execute(self, *, subject, budgeted="0",
                institution_id="",
                period="") -> dict:
        return self._val.validate_program(
            subject=subject, budgeted=budgeted,
            institution_id=institution_id,
            period=period)
