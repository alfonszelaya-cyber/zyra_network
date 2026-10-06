
from __future__ import annotations

class CoordinateInstitutionsUseCase:
    """Propone acuerdo y opcionalmente lo activa."""

    def __init__(self, coordination):
        self._coord = coordination

    def execute(self, *, institutions, subject,
                activate=False) -> dict:
        a = self._coord.propose_agreement(
            institutions=institutions,
            subject=subject)
        if activate:
            a = self._coord.activate(
                a["agreement_id"])
        return a
