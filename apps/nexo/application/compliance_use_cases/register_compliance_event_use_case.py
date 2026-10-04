
from __future__ import annotations
from apps.nexo.domain.compliance.compliance_registry import ComplianceRegistry

class RegisterComplianceEventUseCase:
    def __init__(self, compliance_registry, audit):
        self._engine = compliance_registry
        self._audit = audit

    def execute(self, *, company_id, event_type, description, created_by="nexo"):
        event = self._engine.store({"company_id": company_id, "event_type": event_type,
                                    "description": description})
        self._audit.append(event_type="nexo.compliance.event", actor=created_by,
                           subject=event["event_id"],
                           payload={"company_id": company_id})
        return event
