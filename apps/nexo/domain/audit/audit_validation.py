
"""Validacion de registros de auditoria NEXO."""
from __future__ import annotations

class NexoAuditValidation:
    """Un registro valido lleva event, actor, entity."""

    REQUIRED = ("event", "actor", "entity")

    def validate_record(self, record) -> dict:
        missing = []
        for f in self.REQUIRED:
            if f not in record or record[f] in (None,
                                                ""):
                missing.append(f)
        return {"valid": len(missing) == 0,
                "missing": missing}
