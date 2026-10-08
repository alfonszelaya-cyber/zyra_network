"""SUBASTAS HTTP client to ZYRA Network."""
from __future__ import annotations

import json
import os
import urllib.error
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
        bool, dict | None, str | None,
    ]:
        return self._call("GET", path)

    def post(
        self, path: str, payload: dict,
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
                "ZYRA_URL not set",
            )
        url = self._base + path
        data = None
        headers = {
            "Accept": "application/json",
        }
        if payload is not None:
            data = json.dumps(
                payload
            ).encode("utf-8")
            headers["Content-Type"] = (
                "application/json"
            )
        last_error = "unknown error"
        for _attempt in range(
            self._retries + 1
        ):
            request = urllib.request.Request(
                url,
                data=data,
                headers=headers,
                method=method,
            )
            try:
                with (
                    urllib.request.urlopen(
                        request,
                        timeout=(
                            self._timeout
                        ),
                    )
                ) as response:
                    body = response.read()
                parsed = json.loads(
                    body.decode("utf-8")
                )
                if isinstance(
                    parsed, dict
                ):
                    return (
                        True,
                        parsed,
                        None,
                    )
                return (
                    False,
                    None,
                    "non-dict response",
                )
            except (
                urllib.error.HTTPError
            ) as exc:
                return (
                    False,
                    None,
                    "HTTP "
                    + str(exc.code),
                )
            except Exception as exc:
                last_error = str(exc)
        return (
            False,
            None,
            last_error,
        )
