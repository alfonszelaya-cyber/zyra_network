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
            import traceback as _cap_tb
            _cap_tb.print_exc()
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
            len(s) == 3
            and s[0] == "profile"
            and s[1] == "documents"
        ):
            reg = caps.profiles
            docs = reg.list_documents(zid=s[2])
            asur = reg.assurance_level(zid=s[2])
            self._ok({"documents": list(docs), "assurance": asur})
            return
        if (
            len(s) == 3
            and s[0] == "consent"
            and s[1] == "list"
        ):
            reg = caps.profiles
            self._ok(list(reg.consents_of(zid=s[2])))
            return
        if (
            len(s) == 3
            and s[0] == "bridge"
            and s[1] == "subscriptions"
        ):
            bridge = getattr(
                caps, "bridge", None)
            if bridge is None:
                self._send(
                    503,
                    {
                        "ok": False,
                        "error": {
                        "type":
                        "not_wired"}})
                return
            tipos = (
                bridge.subscriptions(
                    app_id=s[2]))
            self._ok(list(tipos))
            return
        if (
            len(s) == 3
            and s[0] == "documents"
            and s[1] == "list"
        ):
            kind_q = ""
            purpose_q = ""
            if query:
                kind_q = (
                    query.get("kind")
                    or [""]
                )[0]
                purpose_q = (
                    query.get("purpose")
                    or [""]
                )[0]
            docs = (
                caps.exchange
                .list_documents(
                    owner_zid=s[2],
                    kind=(
                        kind_q
                        or None),
                    purpose=(
                        purpose_q
                        or None),
                )
            )
            self._ok(docs)
            return
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
        if s == ["bridge", "relay"]:
            bridge = getattr(
                type(self).caps, "bridge", None)
            if bridge is None:
                self._send(
                    503,
                    {
                        "ok": False,
                        "error": {
                        "type":
                        "not_wired"}})
                return
            resultado = (
                bridge.relay())
            self._send(
                200,
                {
                    "ok": True,
                    "data": (resultado)},
            )
            return
        if s == ["profile", "documents", "add"]:
            reg = caps.profiles
            res = reg.add_document(
                zid=self._req(doc, "zid"),
                doc_type=self._req(doc, "doc_type"),
                doc_number=self._req(doc, "doc_number"),
                issuing_country=self._req(doc, "issuing_country"),
                issuing_authority=str(doc.get("issuing_authority", "")),
                issue_date=str(doc.get("issue_date", "")),
                expiry_date=str(doc.get("expiry_date", "")),
                verified=bool(doc.get("verified", False)),
                verified_by=str(doc.get("verified_by", "")),
            )
            self._send(201, {"ok": True, "data": res})
            return
        if s == ["profile", "documents", "revoke"]:
            caps.profiles.revoke_document(
                zid=self._req(doc, "zid"),
                document_id=self._req(doc, "document_id"),
                reason=str(doc.get("reason", "")))
            self._send(200, {"ok": True})
            return
        if s == ["consent", "grant"]:
            import base64 as _b64c
            bio = getattr(type(self).kernel, "_biometrics", None)
            if bio is None:
                self._error(503, "not_wired", "biometrics not configured")
                return
            zid_c = self._req(doc, "zid")
            selfie_c = _b64c.b64decode(self._req(doc, "selfie_b64"))
            reporte = bio.verify_face(zid_c, selfie_image=selfie_c, actor=zid_c)
            match_c = bool(getattr(reporte, "match", False))
            score_c = float(getattr(reporte, "score", 0.0))
            if not match_c:
                self._error(403, "face_rejected", "biometria no coincide: consentimiento denegado")
                return
            campos_c = tuple(str(doc.get("fields", "")).split(","))
            res = caps.profiles.grant_consent(zid=zid_c, app_id=self._req(doc, "app_id"), fields=campos_c, face_score=score_c, ttl_hours=float(doc.get("ttl_hours", 24)))
            self._send(201, {"ok": True, "data": res})
            return
        if s == ["consent", "revoke"]:
            caps.profiles.revoke_consent(zid=self._req(doc, "zid"), consent_id=self._req(doc, "consent_id"))
            self._send(200, {"ok": True})
            return
        if s == ["freeze"]:
            res = caps.profiles.freeze_zid(zid=self._req(doc, "zid"), reason=str(doc.get("reason", "")))
            self._send(200, {"ok": True, "data": res})
            return
        if s == ["unfreeze"]:
            ok_u = caps.profiles.unfreeze_zid(zid=self._req(doc, "zid"), code=self._req(doc, "unfreeze_code"))
            if not ok_u:
                self._error(403, "bad_code", "codigo de desbloqueo invalido")
                return
            self._send(200, {"ok": True})
            return
        if s == ["documents", "register"]:
            import base64 as _b64
            ex = (type(self).caps.exchange)
            rec = (ex.register_document(
                owner_zid=self._req(
                    doc, "owner_zid"),
                title=self._req(doc, "title"),
                content=_b64.b64decode(
                    self._req(doc, "content_b64")),
                doc_kind=self._req(doc, "doc_kind"),
                purpose=str(doc.get("purpose") or ""),
                storage_ref=str(
                    doc.get("storage_ref") or ""),
                actor_app=self._req(doc, "actor_app"),
                prev_version=(
                    str(doc["prev_version"])
                    if doc.get("prev_version")
                    else None
                ),
            ))
            self._send(
                201,
                {
                    "ok": True,
                    "data": {
                        "document_id": rec["document_id"],
                        "sha256": rec["sha256"],
                        "doc_kind": rec["doc_kind"],
                        "purpose": rec["purpose"],
                        "storage_ref": rec["storage_ref"],
                        "prev_version": rec["prev_version"],
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
