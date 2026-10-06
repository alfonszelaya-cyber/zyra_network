
"""Gobierno familiar: use case (NG9)."""
from __future__ import annotations
from apps.nexo.domain.family_office.family_governance_engine import (
    FamilyGovernanceEngine)

class FamilyGovernanceUseCase:
    """Registrar y consultar decisiones."""

    def __init__(self, governance_engine):
        self._eng = governance_engine

    def execute(self, *, action, subject="",
                participants=None,
                resolution="") -> dict:
        if action == "register":
            return {"decision":
                        self._eng.register_decision(
                            subject=subject,
                            participants=(
                                participants or []),
                            resolution=resolution)}
        if action == "list":
            return {"decisions":
                        self._eng.get_decisions()}
        return {"error": "accion desconocida: "
                + str(action)}
