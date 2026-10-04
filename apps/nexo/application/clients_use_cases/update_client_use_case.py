
from __future__ import annotations
from apps.nexo.domain.clients.client_registry import (
    ClientRegistry)

class UpdateClientUseCase:
    def __init__(self, client_registry:
                 ClientRegistry, audit) -> None:
        self._registry = client_registry
        self._audit = audit

    def execute(self, *, client_id: str,
                updates: dict,
                updated_by: str = "nexo") -> dict:
        client = self._registry.update(client_id, updates)
        if client:
            self._audit.append(
                event_type="nexo.client.updated",
                actor=updated_by, subject=client_id,
                payload=updates)
        return client
