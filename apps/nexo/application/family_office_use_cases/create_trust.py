
from __future__ import annotations
from apps.nexo.domain.family_office.trust_management_engine import (
    TrustManagementEngine)

class CreateTrustUseCase:
    def __init__(self, trust_engine):
        self._engine = trust_engine

    def execute(self, *, trust_name, jurisdiction,
                beneficiaries) -> dict:
        return self._engine.create_trust(
            trust_name=trust_name,
            jurisdiction=jurisdiction,
            beneficiaries=beneficiaries)
