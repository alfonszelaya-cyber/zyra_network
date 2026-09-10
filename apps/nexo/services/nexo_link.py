"""NexoLink: NEXO ops on the Network."""
from __future__ import annotations

import base64

from apps.nexo.infrastructure.network.network_client import (
    NetworkClient,
)


class NexoLink:
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
                "app_id": "nexo",
                "display_name": "NEXO",
                "scopes": [
                    "display_name",
                    "contact",
                ],
            },
        )

    def register_company(
        self, display_name: str
    ) -> tuple[bool, dict | None, str | None]:
        return self._client.post(
            "/identity/register",
            {
                "kind": "organization",
                "display_name": display_name,
                "actor": "nexo",
            },
        )

    def record_fiscal_event(
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
                "actor_app": "nexo",
                "payload": {
                    "event": event,
                    "detail": detail,
                },
            },
        )

    def seal_invoice(
        self,
        *,
        owner_zid: str,
        invoice_id: str,
        content: bytes,
    ) -> tuple[
        bool, dict | None, str | None
    ]:
        encoded = base64.b64encode(
            content
        ).decode("ascii")
        return self._client.post(
            "/documents/seal",
            {
                "owner_zid": owner_zid,
                "title": "Factura "
                + invoice_id,
                "content_b64": encoded,
                "actor_app": "nexo",
            },
        )
