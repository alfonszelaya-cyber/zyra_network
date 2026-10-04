
from __future__ import annotations
from apps.nexo.domain.clients.client_registry import (
    ClientRegistry)

class SegmentClientUseCase:
    def __init__(self, client_registry:
                 ClientRegistry) -> None:
        self._registry = client_registry

    def execute(self, *, client_id: str) -> dict:
        client = self._registry.get_by_id(client_id)
        if not client:
            return {"error": "not_found"}
        score = client.get("total_transactions", 0)
        if score >= 1000:
            segment = "VIP"
        elif score >= 250:
            segment = "PREFERRED"
        elif score >= 50:
            segment = "ACTIVE"
        else:
            segment = "STANDARD"
        self._registry.update(
            client_id, {"segment": segment})
        return {"client_id": client_id,
                "segment": segment}
