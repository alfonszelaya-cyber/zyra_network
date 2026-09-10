"""AxisLink: AXIS ops on the Network."""
from __future__ import annotations

import base64

from apps.axis.infrastructure.network.network_client import (
    NetworkClient,
)


class AxisLink:
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
                "app_id": "axis",
                "display_name": (
                    "AXIS - Salud,"
                    " Justicia y"
                    " Seguridad"
                ),
                "scopes": [
                    "display_name",
                    "contact",
                ],
            },
        )

    def register_person(
        self, display_name: str
    ) -> tuple[
        bool, dict | None, str | None
    ]:
        return self._client.post(
            "/identity/register",
            {
                "kind": "person",
                "display_name": display_name,
                "actor": "axis",
            },
        )

    def record_file_event(
        self,
        zid: str,
        event: str,
        detail: str,
    ) -> tuple[
        bool, dict | None, str | None
    ]:
        return self._client.post(
            "/history/append",
            {
                "zid": zid,
                "entry_type": "other",
                "actor_app": "axis",
                "payload": {
                    "event": event,
                    "detail": detail,
                },
            },
        )

    def seal_evidence(
        self,
        *,
        owner_zid: str,
        evidence_id: str,
        title: str,
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
                "title": "Evidencia "
                + evidence_id,
                "content_b64": encoded,
                "actor_app": "axis",
            },
        )
