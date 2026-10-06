
"""Nexo Workflow Validation - validaciones (NG7)."""
from __future__ import annotations

class NexoWorkflowValidation:
    """Reglas de produccion para workflows."""

    def validate_steps(self, steps) -> dict:
        errors = []
        if not steps or not isinstance(steps,
                                       list):
            errors.append("steps vacio")
        else:
            names = [str(s).strip()
                     for s in steps]
            if any(not n for n in names):
                errors.append(
                    "paso con nombre vacio")
            if len(set(names)) != len(names):
                errors.append(
                    "pasos duplicados")
        return {"valid": len(errors) == 0,
                "errors": errors}

    def validate_payload(self, payload) -> dict:
        ok = payload is None or isinstance(
            payload, dict)
        return {"valid": ok,
                "errors": (["payload debe ser"
                            " objeto"]
                           if not ok else [])}
