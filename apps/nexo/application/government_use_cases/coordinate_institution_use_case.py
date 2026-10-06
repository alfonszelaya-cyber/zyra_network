
from __future__ import annotations

class CoordinateInstitutionUseCase:
    """Envia solicitud interinstitucional."""

    def __init__(self, coordination):
        self._coord = coordination

    def execute(self, *, from_institution,
                to_institution, subject,
                detail="") -> dict:
        return self._coord.send_request(
            from_institution=from_institution,
            to_institution=to_institution,
            subject=subject, detail=detail)
