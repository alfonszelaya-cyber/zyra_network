
"""Planeacion sucesoria: use case (NG9)."""
from __future__ import annotations
from apps.nexo.domain.family_office.succession_engine import (
    SuccessionEngine)

class SuccessionPlanningUseCase:
    """Crear y consultar planes sucesorios."""

    def __init__(self, succession_engine):
        self._eng = succession_engine

    def execute(self, *, action, title="",
                successors=None,
                assets=None) -> dict:
        if action == "create":
            return {"plan":
                        self._eng.create_plan(
                            title=title,
                            successors=(
                                successors or []),
                            assets=(assets or []))}
        if action == "list":
            return {"plans":
                        self._eng.get_plans()}
        return {"error": "accion desconocida: "
                + str(action)}
