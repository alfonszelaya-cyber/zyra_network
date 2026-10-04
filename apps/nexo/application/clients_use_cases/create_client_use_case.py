
from __future__ import annotations
import uuid
from apps.nexo.domain.clients.client_registry import (
    ClientRegistry)

class CreateClientUseCase:
    def __init__(self, client_registry: ClientRegistry,
                 audit) -> None:
        self._registry = client_registry
        self._audit = audit

    def execute(self, *, name: str, email: str,
                phone: str = "",
                created_by: str = "nexo") -> dict:
        client_id = f"CLI-{uuid.uuid4()}"
        client = {"client_id": client_id,
                  "name": name, "email": email,
                  "phone": phone,
                  "status": "ACTIVE"}
        self._registry.store(client)
        self._audit.append(
            event_type="nexo.client.created",
            actor=created_by, subject=client_id,
            payload={"name": name})
        return client
