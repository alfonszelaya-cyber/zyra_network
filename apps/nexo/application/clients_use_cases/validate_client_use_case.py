
from __future__ import annotations
from apps.nexo.domain.clients.client_validation_engine import (
    ClientValidationEngine)

class ValidateClientUseCase:
    def __init__(self, validation_engine:
                 ClientValidationEngine) -> None:
        self._engine = validation_engine

    def execute(self, *, client_data: dict) -> bool:
        return self._engine.validate(client_data)
