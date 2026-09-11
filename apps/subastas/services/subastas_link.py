"""SUBASTAS link to the ZYRA Network.

Resilience rule: every network call is tried
first; if the network rejects or is down, the
app falls back to local operation and survives
(same principle proven in AGRO and NEXO).
"""
from __future__ import annotations

import uuid

_REGISTER_CANDIDATES: tuple[dict, ...] = (
    {
        "app_id": "subastas",
        "name": "SUBASTAS",
        "display_name": "SUBASTAS",
        "roles": [
            "vendedor",
            "comprador",
            "gobierno",
        ],
    },
    {
        "app_id": "subastas",
        "name": "SUBASTAS",
    },
    {
        "app_id": "subastas",
    },
    {},
)


def _find_value(doc, keys):
    if isinstance(doc, dict):
        for k, v in doc.items():
            if str(k).lower() in keys:
                return v
        for v in doc.values():
            found = _find_value(v, keys)
            if found is not None:
                return found
    elif isinstance(doc, list):
        for item in doc:
            found = _find_value(
                item, keys
            )
            if found is not None:
                return found
    return None


class SubastasLink:
    def __init__(self, client) -> None:
        self._client = client

    def register_app(self) -> tuple[
        bool, dict | None,
    ]:
        last_error = "unknown"
        for payload in (
            _REGISTER_CANDIDATES
        ):
            ok, data, err = (
                self._client.post(
                    "/apps/register",
                    payload,
                )
            )
            if ok:
                return (True, data)
            if err:
                last_error = err
        return (
            True,
            {
                "registered":
                "local-fallback",
                "app_id": "subastas",
                "last_error": (
                    last_error
                ),
            },
        )

    def register_account(
        self, name: str,
    ) -> tuple[bool, dict | None]:
        payloads = (
            {
                "name": name,
                "display_name": name,
                "kind": "person",
            },
            {
                "name": name,
                "display_name": name,
            },
            {"name": name},
            {"display_name": name},
        )
        for payload in payloads:
            ok, data, _err = (
                self._client.post(
                    "/identity/register",
                    payload,
                )
            )
            if ok and data:
                zid = _find_value(
                    data, ("zid",)
                )
                if isinstance(
                    zid, str
                ) and zid.startswith(
                    "ZID-"
                ):
                    return (
                        True,
                        {"zid": zid},
                    )
        return (
            True,
            {
                "zid": "ZID-"
                + uuid.uuid4().hex[:12],
                "source": "local",
            },
        )

    def give_reputation(
        self,
        *,
        subject_zid: str,
        actor_zid: str,
        kind: str,
        evidence: str,
    ) -> tuple[bool, dict | None]:
        payloads = (
            {
                "subject_zid": (
                    subject_zid
                ),
                "actor_zid": actor_zid,
                "kind": kind,
                "evidence": evidence,
            },
            {
                "subject_zid": (
                    subject_zid
                ),
                "author_zid": actor_zid,
                "kind": kind,
                "evidence": evidence,
            },
            {
                "subject": subject_zid,
                "actor": actor_zid,
                "kind": kind,
                "evidence": evidence,
            },
            {
                "subject_zid": (
                    subject_zid
                ),
                "actor_zid": actor_zid,
                "polarity": kind,
                "comment": evidence,
            },
        )
        for payload in payloads:
            ok, data, _err = (
                self._client.post(
                    "/reputation/record",
                    payload,
                )
            )
            if ok:
                return (True, data)
        return (
            True,
            {
                "recorded": "local",
                "subject_zid": (
                    subject_zid
                ),
                "kind": kind,
                "evidence": evidence,
            },
        )
