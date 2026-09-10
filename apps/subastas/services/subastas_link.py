"""SubastasLink: marketplace ops on the Network.
Never raises - resilience rule."""
from __future__ import annotations

import base64

from apps.subastas.infrastructure.network.network_client import (
    NetworkClient,
)


class SubastasLink:
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
                "app_id": "subastas",
                "display_name": (
                    "SUBASTAS - Mercado"
                ),
                "scopes": [
                    "display_name",
                    "contact",
                ],
            },
        )

    def register_account(
        self,
        display_name: str,
    ) -> tuple[bool, dict | None, str | None]:
        return self._client.post(
            "/identity/register",
            {
                "kind": "person",
                "display_name": display_name,
                "actor": "subastas",
            },
        )

    def seal_listing(
        self,
        *,
        owner_zid: str,
        listing_id: str,
        title: str,
        description: str,
    ) -> tuple[bool, dict | None, str | None]:
        content = (
            "LISTING|"
            + listing_id
            + "|"
            + title
            + "|"
            + description
        ).encode("utf-8")
        encoded = base64.b64encode(
            content
        ).decode("ascii")
        return self._client.post(
            "/documents/seal",
            {
                "owner_zid": owner_zid,
                "title": "Listado: "
                + title,
                "content_b64": encoded,
                "actor_app": "subastas",
            },
        )

    def give_reputation(
        self,
        subject_zid: str,
        actor_zid: str,
        kind: str,
        evidence: str,
    ) -> tuple[bool, dict | None, str | None]:
        evidence_b64 = base64.b64encode(
            evidence.encode("utf-8")
        ).decode("ascii")
        return self._client.post(
            "/reputation/record",
            {
                "subject_zid": subject_zid,
                "actor_zid": actor_zid,
                "kind": kind,
                "evidence_b64": (
                    evidence_b64
                ),
            },
        )
