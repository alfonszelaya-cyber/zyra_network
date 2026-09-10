"""MpeLink: MPE operations on the Network."""
from __future__ import annotations

import base64

from apps.mi_primer_empleo.infrastructure.network.network_client import (
    NetworkClient,
)


class MpeLink:
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
                "app_id": "mpe",
                "display_name": (
                    "Mi Primer Empleo"
                ),
                "scopes": [
                    "display_name",
                    "contact",
                ],
            },
        )

    def register_user(
        self, display_name: str
    ) -> tuple[bool, dict | None, str | None]:
        return self._client.post(
            "/identity/register",
            {
                "kind": "person",
                "display_name": display_name,
                "actor": "mpe",
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
                "actor": "mpe",
            },
        )

    def complete_trust(
        self, zid: str
    ) -> tuple[bool, dict | None, str | None]:
        return self._client.post(
            "/trust/complete",
            {"zid": zid, "actor": "mpe"},
        )

    def is_trusted(
        self, zid: str
    ) -> tuple[bool, dict | None, str | None]:
        return self._client.get(
            f"/trust/{zid}"
        )

    def record_work_event(
        self,
        zid: str,
        event: str,
        detail: str,
    ) -> tuple[bool, dict | None, str | None]:
        return self._client.post(
            "/history/append",
            {
                "zid": zid,
                "entry_type": "employment",
                "actor_app": "mpe",
                "payload": {
                    "event": event,
                    "detail": detail,
                },
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

    def reputation_score(
        self, zid: str
    ) -> tuple[bool, dict | None, str | None]:
        return self._client.get(
            f"/reputation/{zid}"
        )
