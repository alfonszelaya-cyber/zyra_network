
from __future__ import annotations
from apps.nexo.domain.clients.client_registry import (
    ClientRegistry)

class RegisterClientHistoryUseCase:
    def __init__(self, client_registry:
                 ClientRegistry) -> None:
        self._registry = client_registry

    def execute(self, *, client_id: str,
                event_type: str,
                description: str) -> dict:
        return self._registry.register_history(
            client_id=client_id,
            history_event={
                "event_type": event_type,
                "description": description})
