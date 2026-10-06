
from __future__ import annotations

class ValidateRegulatoryComplianceUseCase:
    """Registra requisito, lo verifica y devuelve tasa
    de cumplimiento (informativo, regla 57)."""

    def __init__(self, compliance):
        self._comp = compliance

    def execute(self, *, institution_id,
                requirement, compliant) -> dict:
        r = self._comp.register_requirement(
            institution_id=institution_id,
            requirement=requirement)
        if compliant:
            self._comp.mark_compliant(
                r["requirement_id"])
        else:
            self._comp.mark_violation(
                r["requirement_id"])
        return self._comp.compliance_rate(
            institution_id)
