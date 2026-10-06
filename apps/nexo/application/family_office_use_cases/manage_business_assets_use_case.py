
"""Activos Empresariales: use case (NG9)."""
from __future__ import annotations
from apps.nexo.domain.family_office.business_assets_engine import (
    BusinessAssetsEngine)

class ManageBusinessAssetsUseCase:
    """Alta, listado y valor total."""

    def __init__(self, engine):
        self._eng = engine

    def execute(self, *, action, company_id,
                **kwargs) -> dict:
        if action == "register":
            return {"registered":
                        self._eng.register(
                            company_id=company_id,
                            **kwargs)}
        if action == "list":
            return {"assets":
                        self._eng.list_for(
                            company_id)}
        if action == "total":
            return {"total":
                        self._eng.total_value(
                            company_id)}
        return {"error": "accion desconocida: "
                + str(action)}
