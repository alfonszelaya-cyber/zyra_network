
from __future__ import annotations
from apps.nexo.domain.family_office.inheritance_engine import (
    InheritanceEngine)

class InheritancePlanningUseCase:
    def __init__(self, inheritance_engine):
        self._engine = inheritance_engine

    def execute(self, *, estate_name, beneficiaries,
                total_value) -> dict:
        return self._engine.create_inheritance(
            estate_name=estate_name,
            beneficiaries=beneficiaries,
            total_value=total_value)
