
from __future__ import annotations
from apps.nexo.domain.clients.client_registry import (
    ClientRegistry)

class GenerateClientProfileUseCase:
    def __init__(self, client_registry:
                 ClientRegistry) -> None:
        self._registry = client_registry

    def execute(self, *, client_id: str) -> dict:
        client = self._registry.get_by_id(client_id)
        if not client:
            return {"error": "not_found"}
        return {"client_id": client_id,
                "name": client.get("name"),
                "email": client.get("email"),
                "phone": client.get("phone"),
                "status": client.get("status"),
                "profile": client}
