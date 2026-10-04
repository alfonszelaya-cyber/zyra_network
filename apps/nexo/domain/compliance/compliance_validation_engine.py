
"""Compliance Validation - NEXO / ZYRA."""
from __future__ import annotations
from typing import Dict

class ComplianceValidationEngine:
    """Valida operaciones contra reglas basicas."""

    def validate(self, *, operation_data):
        violations = []
        warnings = []
        try:
            amt = float(operation_data.get("amount", 0))
        except Exception:
            amt = 0
        if amt <= 0:
            violations.append("INVALID_AMOUNT")
        if not operation_data.get("counterparty"):
            warnings.append("NO_COUNTERPARTY")
        if operation_data.get("sanctioned", False):
            violations.append("SANCTIONED_COUNTERPARTY")
        return {"is_valid": len(violations) == 0,
                "violations": violations,
                "warnings": warnings}
