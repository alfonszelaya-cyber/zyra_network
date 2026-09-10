"""HTTP surface for the trust services.

Companion to runtime/api.py: same envelope style
({"ok": true, "data": ...}) and optional bearer
token, but bound to ZyraCapabilities so consumers
(family demo, apps) reach the trust services over
HTTP. The engines themselves enforce registered-
apps authorization; the token guards everything
past /health when configured.

Served by CapabilitiesServer, the counterpart of
ZyraServer (daemon threads, reusable address,
bound_port for ephemeral binds).
"""
from __future__ import annotations

import base64
import hmac
import json
from dataclasses import dataclass
from http.server import (
    BaseHTTPRequestHandler,
    ThreadingHTTPServer,
)
from typing import Any, ClassVar
from urllib.parse import parse_qs, urlparse

from shared_engines.common.errors import (
    EngineError,
)
from shared_engines.runtime.capabilities import (
    ZyraCapabilities,
)


@dataclass(frozen=True)
class _ApiError(Exception):
    status: int
    code: str
    message: str


class CapabilitiesApiHandler(
    BaseHTTPRequestHandler
):
    caps: ClassVar[ZyraCapabilities]
    token: ClassVar[str | None] = None

    def log_message(
        self,
        format: str,
        *args: object,
    ) -> None:
        return None

    def do_GET(self) -> None:
        self._dispatch("GET")

    def do_POST(self) -> None:
        self._dispatch("POST")

    def _dispatch(
        self, method: str
    ) -> None:
        try:
            self._route(method)
        except _ApiError as exc:
            self._error(
                exc.status,
                exc.code,
                exc.message,
            )
        except PermissionError as exc:
            self._error(
                403,
                "forbidden",
                str(exc),
            )
        except (EngineError, ValueError) as exc:
            self._error(
                400,
                "invalid_request",
                str(exc),
            )
        except Exception:
            self._error(
                500,
                "internal_error",
                "internal error",
            )

    def _authorized(self) -> None:
        token = type(self).token
        if token is None:
            return
        header = self.headers.get(
            "Authorization"
        )
        if header is None or not hmac.compare_digest(
            header,
            f"Bearer {token}",
        ):
            raise _ApiError(
                401,
                "unauthorized",
                "valid bearer token"
                " required",
            )

    def _route(
        self, method: str
    ) -> None:
        parsed = urlparse(self.path)
        segments = [
            s
            for s in parsed.path.split("/")
            if s
        ]
        if segments == ["health"]:
            if method != "GET":
                raise _ApiError(
                    405,
                    "method_not_allowed",
                    "use GET",
                )
            self._send(
                200,
                {
                    "ok": True,
                    "data": {
                        "service":
                        "zyra-capabilities",
                        "status": "up",
                    },
                },
            )
            return
        self._authorized()
        query = parse_qs(parsed.query)
        if method == "GET":
            self._route_get(
                segments, query
            )
        else:
            self._route_post(segments)

    def _route_get(
        self,
        s: list[str],
        query: dict[str, list[str]],
    ) -> None:
        caps = type(self).caps
        if (
            len(s) == 2
            and s[0] == "trust"
        ):
            trusted = caps.trust.is_trusted(
                zid=s[1]
            )
            self._ok(
                {
                    "zid": s[1],
                    "trusted": trusted,
                }
            )
            return
        if (
            len(s) == 2
            and s[0] == "profile"
        ):
            app = query.get("app", [""])[0]
            if not app:
                raise ValueError(
                    "missing app query"
                    " parameter"
                )
            view = (
                caps.profiles.view_for_app(
                    app_id=app,
                    zid=s[1],
                )
            )
            self._ok(
                {
                    "zid": view.zid,
                    "fields": view.fields,
                    "levels": view.levels,
                }
            )
            return
        if (
            len(s) == 2
            and s[0] == "history"
        ):
            timeline = caps.history.timeline(
                zid=s[1]
            )
            self._ok(
                [
                    {
                        "seq": e.entry_seq,
                        "type": (
                            e.entry_type
                        ),
                        "actor": (
                            e.actor_app
                        ),
                        "payload": (
                            e.payload
                        ),
                        "content_hash": (
                            e.content_hash
                        ),
                    }
                    for e in timeline
                ]
            )
            return
        if (
            len(s) == 2
            and s[0] == "reputation"
        ):
            summary = (
                caps.reputation.summary(
                    subject_zid=s[1]
                )
            )
            self._ok(
                {
                    "zid": (
                        summary.subject_zid
                    ),
                    "score": summary.score,
                    "positive": (
                        summary.positive_events
                    ),
                    "negative": (
                        summary.negative_events
                    ),
                }
            )
            return
        if (
            len(s) == 2
            and s[0] == "certificates"
        ):
            records = (
                caps.certification
                .list_by_subject(
                    subject_zid=s[1]
                )
            )
            self._ok(
                [
                    {
                        "certificate_id": r.certificate_id,
                        "scope": r.scope,
                        "title": r.title,
                        "revoked": r.revoked,
                    }
                    for r in records
                ]
            )
            return
        raise _ApiError(
            404,
            "not_found",
            "unknown route",
        )

    def _route_post(
        self, s: list[str]
    ) -> None:
        caps = type(self).caps
        doc = self._read_json()
        if s == ["apps", "register"]:
            scopes_raw = doc.get("scopes")
            if not isinstance(
                scopes_raw, list
            ):
                raise ValueError(
                    "scopes must be a"
                    " list"
                )
            record = (
                caps.profiles.register_app(
                    app_id=self._req(
                        doc, "app_id"
                    ),
                    display_name=self._req(
                        doc,
                        "display_name",
                    ),
                    scopes=tuple(
                        str(x)
                        for x in scopes_raw
                    ),
                )
            )
            self._send(
                201,
                {
                    "ok": True,
                    "data": {
                        "app_id": (
                            record.app_id
                        ),
                        "scopes": list(
                            record.scopes
                        ),
                    },
                },
            )
            return
        if s == ["profile", "field"]:
            caps.profiles.set_field(
                zid=self._req(doc, "zid"),
                field=self._req(
                    doc, "field"
                ),
                value=self._req(
                    doc, "value"
                ),
                verified=bool(
                    doc.get(
                        "verified", False
                    )
                ),
            )
            self._ok({"saved": True})
            return
        if s == ["trust", "complete"]:
            final = (
                caps.trust.onboarding_complete(
                    zid=self._req(
                        doc, "zid"
                    ),
                    actor=self._req(
                        doc, "actor"
                    ),
                )
            )
            self._ok(
                {
                    "zid": final.zid,
                    "status": (
                        final.status.value
                    ),
                }
            )
            return
        if s == ["history", "append"]:
            payload = doc.get("payload")
            if not isinstance(
                payload, dict
            ):
                raise ValueError(
                    "payload must be an"
                    " object"
                )
            typed_payload: dict[
                str, object
            ] = {
                str(k): v
                for k, v in payload.items()
            }
            entry = caps.history.append(
                zid=self._req(doc, "zid"),
                entry_type=self._req(
                    doc, "entry_type"
                ),
                actor_app=self._req(
                    doc, "actor_app"
                ),
                payload=typed_payload,
            )
            self._send(
                201,
                {
                    "ok": True,
                    "data": {
                        "seq": (
                            entry.entry_seq
                        ),
                        "content_hash": entry.content_hash,
                    },
                },
            )
            return
        if s == ["documents", "seal"]:
            sealed = (
                caps.exchange.seal_document(
                    owner_zid=self._req(
                        doc, "owner_zid"
                    ),
                    title=self._req(
                        doc, "title"
                    ),
                    content=self._b64(
                        self._req(
                            doc,
                            "content_b64",
                        )
                    ),
                    actor_app=self._req(
                        doc, "actor_app"
                    ),
                )
            )
            self._send(
                201,
                {
                    "ok": True,
                    "data": {
                        "document_id": sealed.document_id,
                        "sha256": sealed.sha256,
                        "signature_b64": base64.b64encode(
                            sealed.network_signature
                        ).decode("ascii"),
                        "public_pem": sealed.public_pem.decode(
                            "utf-8"
                        ),
                    },
                },
            )
            return
        if s == ["documents", "verify"]:
            verdict = (
                caps.exchange.verify_document(
                    document_id=self._req(
                        doc,
                        "document_id",
                    ),
                    content=self._b64(
                        self._req(
                            doc,
                            "content_b64",
                        )
                    ),
                )
            )
            self._ok(
                {
                    "authentic": verdict.authentic,
                    "hash_matches": verdict.hash_matches,
                    "signature_valid": verdict.signature_valid,
                }
            )
            return
        if s == ["search"]:
            result = caps.search.search(
                app_id=self._req(
                    doc, "app_id"
                ),
                query=self._req(
                    doc, "query"
                ),
            )
            self._ok(
                {
                    "total": result.total,
                    "items": [
                        {
                            "source": h.source,
                            "ref_id": h.ref_id,
                            "title": h.title,
                            "score": h.score,
                        }
                        for h in result.items
                    ],
                }
            )
            return
        if s == ["reputation", "record"]:
            event = (
                caps.reputation.record_event(
                    subject_zid=self._req(
                        doc,
                        "subject_zid",
                    ),
                    actor_zid=self._req(
                        doc, "actor_zid"
                    ),
                    kind=self._req(
                        doc, "kind"
                    ),
                    evidence=self._b64(
                        self._req(
                            doc,
                            "evidence_b64",
                        )
                    ),
                )
            )
            self._send(
                201,
                {
                    "ok": True,
                    "data": {
                        "event_id": event.event_id,
                        "seq": event.seq,
                    },
                },
            )
            return
        if s == ["export"]:
            entries_raw = doc.get("entries")
            if not isinstance(
                entries_raw, list
            ):
                raise ValueError(
                    "entries must be a"
                    " list"
                )
            entries: tuple[
                tuple[str, str, str], ...
            ] = tuple(
                (
                    str(e[0]),
                    str(e[1]),
                    str(e[2]),
                )
                for e in entries_raw
                if isinstance(e, list)
                and len(e) == 3
            )
            bundle = (
                caps.export.export_bundle(
                    subject_zid=self._req(
                        doc,
                        "subject_zid",
                    ),
                    entries=entries,
                    actor_app=self._req(
                        doc, "actor_app"
                    ),
                )
            )
            self._send(
                201,
                {
                    "ok": True,
                    "data": {
                        "bundle_id": bundle.bundle_id,
                        "manifest_sha256": bundle.manifest_sha256,
                    },
                },
            )
            return
        raise _ApiError(
            404,
            "not_found",
            "unknown route",
        )

    def _read_json(
        self,
    ) -> dict[str, Any]:
        length_header = self.headers.get(
            "Content-Length"
        )
        if length_header is None:
            raise _ApiError(
                411,
                "length_required",
                "Content-Length required",
            )
        try:
            length = int(length_header)
        except ValueError as exc:
            raise _ApiError(
                400,
                "invalid_request",
                "bad Content-Length",
            ) from exc
        if length > 10_000_000:
            raise _ApiError(
                413,
                "payload_too_large",
                "body exceeds limit",
            )
        raw = self.rfile.read(length)
        try:
            parsed: Any = json.loads(
                raw.decode("utf-8")
            )
        except (
            UnicodeDecodeError,
            ValueError,
        ) as exc:
            raise _ApiError(
                400,
                "invalid_json",
                "body is not valid JSON",
            ) from exc
        if not isinstance(parsed, dict):
            raise _ApiError(
                400,
                "invalid_request",
                "body must be a JSON"
                " object",
            )
        return {
            str(k): v
            for k, v in parsed.items()
        }

    @staticmethod
    def _req(
        doc: dict[str, Any], key: str
    ) -> str:
        value: Any = doc.get(key)
        if isinstance(value, int) and not isinstance(
            value, bool
        ):
            value = str(value)
        if not isinstance(value, str):
            raise ValueError(
                f"missing field: {key}"
            )
        if not value.strip():
            raise ValueError(
                f"missing field: {key}"
            )
        return value

    @staticmethod
    def _b64(value: str) -> bytes:
        try:
            return base64.b64decode(
                value, validate=True
            )
        except ValueError as exc:
            raise ValueError(
                "invalid base64 payload"
            ) from exc

    def _ok(self, data: Any) -> None:
        self._send(
            200,
            {"ok": True, "data": data},
        )

    def _error(
        self,
        status: int,
        code: str,
        message: str,
    ) -> None:
        self._send(
            status,
            {
                "ok": False,
                "error": {
                    "type": code,
                    "message": message,
                },
            },
        )

    def _send(
        self,
        status: int,
        payload: dict[str, Any],
    ) -> None:
        body = json.dumps(payload).encode(
            "utf-8"
        )
        self.send_response(status)
        self.send_header(
            "Content-Type",
            "application/json",
        )
        self.send_header(
            "Content-Length",
            str(len(body)),
        )
        self.end_headers()
        self.wfile.write(body)


class CapabilitiesServer(ThreadingHTTPServer):
    """Counterpart of ZyraServer for the
    capabilities surface."""

    daemon_threads = True
    allow_reuse_address = True

    def __init__(
        self,
        address: tuple[str, int],
    ) -> None:
        super().__init__(
            address, CapabilitiesApiHandler
        )

    @property
    def bound_port(self) -> int:
        return int(self.server_address[1])


def serve_capabilities(
    caps: ZyraCapabilities,
    *,
    host: str = "127.0.0.1",
    port: int = 0,
    token: str | None = None,
) -> CapabilitiesServer:
    """Bind caps and start serving."""
    CapabilitiesApiHandler.caps = caps
    CapabilitiesApiHandler.token = token
    return CapabilitiesServer((host, port))
