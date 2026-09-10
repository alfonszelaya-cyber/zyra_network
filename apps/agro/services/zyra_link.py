"""ZyraLink: high-level AGRO operations on the
Network. Never raises - resilience rule."""
from __future__ import annotations

from apps.agro.infrastructure.network.network_client import (
    NetworkClient,
)


class ZyraLink:
    """Trust operations for producers."""

    def __init__(
        self, client: NetworkClient
    ) -> None:
        self._client = client

    def register_app(self) -> tuple[
        bool, dict | None, str | None
    ]:
        return self._client.post(
            "/apps/register",
            {
                "app_id": "agro",
                "display_name": (
                    "AGRO - Productores"
                ),
                "scopes": [
                    "display_name",
                    "contact",
                    "address",
                ],
            },
        )

    def register_producer_zid(
        self, display_name: str
    ) -> tuple[bool, dict | None, str | None]:
        return self._client.post(
            "/identity/register",
            {
                "kind": "person",
                "display_name": display_name,
                "actor": "agro",
            },
        )

    def complete_trust(
        self, zid: str
    ) -> tuple[bool, dict | None, str | None]:
        return self._client.post(
            "/trust/complete",
            {"zid": zid, "actor": "agro"},
        )

    def is_trusted(
        self, zid: str
    ) -> tuple[bool, dict | None, str | None]:
        return self._client.get(
            f"/trust/{zid}"
        )

    def record_agro_event(
        self,
        zid: str,
        event: str,
        detail: str,
    ) -> tuple[bool, dict | None, str | None]:
        return self._client.post(
            "/history/append",
            {
                "zid": zid,
                "entry_type": "other",
                "actor_app": "agro",
                "payload": {
                    "event": event,
                    "detail": detail,
                },
            },
        )
