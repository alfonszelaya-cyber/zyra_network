"""CICLO link extension - ADD-ONLY module."""
from __future__ import annotations

import base64


class CicloLinkExt:
    def __init__(self, client) -> None:
        self._client = client

    def complete_trust(self, zid: str) -> bool:
        try:
            ok, _d, _e = self._client.post(
                "/trust/complete",
                {"zid": zid, "actor": "ciclo"},
            )
            return bool(ok)
        except Exception:
            return False

    def seal_document(
        self,
        *,
        owner_zid: str,
        title: str,
        content: str,
    ) -> tuple[bool, str | None]:
        encoded = base64.b64encode(
            content.encode("utf-8")
        ).decode("ascii")
        try:
            ok, data, _err = self._client.post(
                "/documents/seal",
                {
                    "owner_zid": owner_zid,
                    "title": title,
                    "content_b64": encoded,
                    "actor_app": "ciclo",
                },
            )
        except Exception:
            return (False, None)
        if ok and data:
            doc_id = self._find_key(
                data, ("document_id", "seal_id")
            )
            if isinstance(doc_id, str):
                return (True, doc_id)
        return (False, None)

    def earn_tokens(
        self, *, subject_zid: str, activity: str, ref_id: str,
    ) -> tuple[bool, dict | None]:
        try:
            ok, data, _err = self._client.post(
                "/tokens/earn",
                {
                    "subject_zid": subject_zid,
                    "activity": activity,
                    "ref_type": "reciclaje",
                    "ref_id": ref_id,
                },
            )
            return (bool(ok), data)
        except Exception:
            return (False, None)

    @staticmethod
    def _find_key(doc, keys):
        if isinstance(doc, dict):
            for key, value in doc.items():
                if str(key).lower() in keys:
                    return value
            for value in doc.values():
                found = CicloLinkExt._find_key(value, keys)
                if found is not None:
                    return found
        elif isinstance(doc, list):
            for item in doc:
                found = CicloLinkExt._find_key(item, keys)
                if found is not None:
                    return found
        return None
