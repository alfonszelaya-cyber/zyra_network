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

    def enroll_person(
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
            "actor": "axis",
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
