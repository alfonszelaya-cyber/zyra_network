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

    def enroll_producer(
        self,
        *,
        display_name: str,
        doc_image_b64: str,
        selfie_image_b64: str,
        doc_kind: str | None = None,
        doc_country: str | None = None,
        doc_number: str | None = None,
    ) -> tuple[bool, dict | None, str | None]:
        payload: dict = {
            "kind": "person",
            "display_name": display_name,
            "actor": "agro",
            "doc_image_b64": doc_image_b64,
            "selfie_image_b64": selfie_image_b64,
        }
        if doc_kind:
            payload["doc_kind"] = doc_kind
        if doc_country:
            payload["doc_country"] = doc_country
        if doc_number:
            payload["doc_number"] = doc_number
        return self._client.post(
            "/identity/enroll", payload
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
