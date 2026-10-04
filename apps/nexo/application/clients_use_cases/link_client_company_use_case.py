
from __future__ import annotations
from apps.nexo.domain.clients.client_registry import (
    ClientRegistry)

class LinkClientCompanyUseCase:
    def __init__(self, client_registry:
                 ClientRegistry, audit) -> None:
        self._registry = client_registry
        self._audit = audit

    def execute(self, *, client_id: str,
                company_id: str,
                linked_by: str = "nexo") -> dict:
        result = self._registry.link_company(
            client_id=client_id,
            company_id=company_id)
        self._audit.append(
            event_type="nexo.client.company_linked",
            actor=linked_by, subject=client_id,
            payload={"company_id": company_id})
        return result
