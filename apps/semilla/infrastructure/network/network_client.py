"""SEMILLA HTTP client to ZYRA Network."""
from __future__ import annotations

import json
import os
import urllib.request


class NetworkClient:
    def __init__(
        self,
        base_url: str | None = None,
        *,
        timeout_seconds: float = 5.0,
        max_retries: int = 2,
    ) -> None:
        self._base = (
            base_url
            or os.environ.get("ZYRA_URL", "")
        ).rstrip("/")
        self._timeout = timeout_seconds
        self._retries = max(0, max_retries)

    def get(self, path: str) -> tuple[
        bool, dict | None, str | None
    ]:
        return self._call("GET", path)

    def post(
        self, path: str, payload: dict
    ) -> tuple[bool, dict | None, str | None]:
        return self._call("POST", path, payload)

    def _call(
        self,
        method: str,
        path: str,
        payload: dict | None = None,
    ) -> tuple[bool, dict | None, str | None]:
        if not self._base:
            return (
                False,
                None,
                "ZYRA_URL not configured",
            )
        url = self._base + path
        data = None
        if payload is not None:
            data = json.dumps(
                payload
            ).encode("utf-8")
        last_error = "unknown"
        for attempt in range(
            self._retries + 1
        ):
            try:
                request = urllib.request.Request(
                    url,
                    data=data,
                    method=method,
                    headers={
                        "Content-Type":
                        "application/json"
                    },
                )
                with urllib.request.urlopen(
                    request,
                    timeout=self._timeout,
                ) as response:
                    body = json.loads(
                        response.read()
                        .decode("utf-8")
                    )
                if body.get("ok") is True:
                    return (
                        True,
                        body.get("data"),
                        None,
                    )
                error = body.get("error", {})
                return (
                    False,
                    None,
                    str(
                        error.get(
                            "message",
                            "rejected",
                        )
                    ),
                )
            except Exception as exc:
                last_error = str(exc)
        return False, None, last_error
