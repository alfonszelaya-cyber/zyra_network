"""CicloLink: CICLO-DIGITAL ops on the Network.
Never raises - resilience rule."""
from __future__ import annotations

import base64

from apps.ciclo_digital.infrastructure.network.network_client import (
    NetworkClient,
)


class CicloLink:
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
                "app_id": "ciclo",
                "display_name": (
                    "CICLO-DIGITAL"
                ),
                "scopes": [
                    "display_name",
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
                "actor": "ciclo",
            },
        )

    def seal_recycled(
        self,
        *,
        owner_zid: str,
        item_id: str,
        description: str,
    ) -> tuple[
        bool, dict | None, str | None
    ]:
        content = (
            "RECICLADO|"
            + item_id
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
                "title": "Reciclado "
                + item_id,
                "content_b64": encoded,
                "actor_app": "ciclo",
            },
        )

    def earn_tokens(
        self,
        *,
        subject_zid: str,
        activity: str,
        ref_id: str,
    ) -> tuple[
        bool, dict | None, str | None
    ]:
        return self._client.post(
            "/tokens/earn",
            {
                "subject_zid": subject_zid,
                "activity": activity,
                "ref_type": "reciclaje",
                "ref_id": ref_id,
            },
        )

    def token_balance(
        self, zid: str
    ) -> tuple[
        bool, dict | None, str | None
    ]:
        return self._client.get(
            "/tokens/" + zid + "/balance"
        )

    def search_network(
        self,
        *,
        app_id: str,
        query: str,
    ) -> tuple[
        bool, dict | None, str | None
    ]:
        return self._client.post(
            "/search",
            {
                "app_id": app_id,
                "query": query,
            },
        )

    def export_evidence(
        self,
        *,
        subject_zid: str,
        entries: list[list[str]],
    ) -> tuple[
        bool, dict | None, str | None
    ]:
        return self._client.post(
            "/export",
            {
                "subject_zid": subject_zid,
                "entries": entries,
                "actor_app": "ciclo",
            },
        )
