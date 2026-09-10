"""SemillaLink: SEMILLA ops on the Network."""
from __future__ import annotations

from apps.semilla.infrastructure.network.network_client import (
    NetworkClient,
)


class SemillaLink:
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
                "app_id": "semilla",
                "display_name": (
                    "SEMILLA - Educacion"
                ),
                "scopes": [
                    "display_name",
                    "contact",
                ],
            },
        )

    def register_person(
        self,
        display_name: str,
        kind: str = "person",
    ) -> tuple[bool, dict | None, str | None]:
        return self._client.post(
            "/identity/register",
            {
                "kind": kind,
                "display_name": display_name,
                "actor": "semilla",
            },
        )

    def record_milestone(
        self,
        zid: str,
        milestone: str,
        detail: str,
    ) -> tuple[bool, dict | None, str | None]:
        return self._client.post(
            "/history/append",
            {
                "zid": zid,
                "entry_type": "education",
                "actor_app": "semilla",
                "payload": {
                    "milestone": milestone,
                    "detail": detail,
                },
            },
        )

    def give_star(
        self,
        subject_zid: str,
        actor_zid: str,
        reason: str,
    ) -> tuple[bool, dict | None, str | None]:
        import base64

        evidence = base64.b64encode(
            reason.encode("utf-8")
        ).decode("ascii")
        return self._client.post(
            "/reputation/record",
            {
                "subject_zid": (
                    subject_zid
                ),
                "actor_zid": actor_zid,
                "kind": "positive",
                "evidence_b64": evidence,
            },
        )
