
from __future__ import annotations
from apps.nexo.domain.compliance.compliance_validation_engine import ComplianceValidationEngine

class ValidateComplianceUseCase:
    def __init__(self, validation_engine):
        self._engine = validation_engine

    def execute(self, *, operation_data):
        return self._engine.validate(operation_data=operation_data)
