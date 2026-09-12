"""AXIS link extension - ADD-ONLY module."""
from __future__ import annotations

import base64


class AxisLinkExt:
    def __init__(self, client) -> None:
        self._client = client

    def complete_trust(self, zid: str) -> bool:
        try:
            ok, _d, _e = self._client.post(
                "/trust/complete",
                {"zid": zid, "actor": "axis"},
            )
            return bool(ok)
        except Exception:
            return False

    def seal_evidence_canonical(
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
                    "actor_app": "axis",
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

    def append_history(
        self, *, zid: str, event: str, detail: str,
    ) -> bool:
        try:
            ok, _d, _e = self._client.post(
                "/history/append",
                {
                    "zid": zid,
                    "entry_type": "health",
                    "actor_app": "axis",
                    "payload": {
                        "event": event,
                        "detail": detail,
                    },
                },
            )
            return bool(ok)
        except Exception:
            return False

    @staticmethod
    def _find_key(doc, keys):
        if isinstance(doc, dict):
            for key, value in doc.items():
                if str(key).lower() in keys:
                    return value
            for value in doc.values():
                found = AxisLinkExt._find_key(value, keys)
                if found is not None:
                    return found
        elif isinstance(doc, list):
            for item in doc:
                found = AxisLinkExt._find_key(item, keys)
                if found is not None:
                    return found
        return None
