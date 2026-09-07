"""HTTP API over the kernel: stable routes, auth, envelopes.

Routes (all JSON):
  GET  /health                                    (no auth)
  POST /identity/register
  GET  /identity/{zid}
  POST /identity/transition
  POST /verification/media
  POST /verification/media/verify
  GET  /verification/media/{media_id}
  GET  /verification/media/{media_id}/history
  POST /verification/credentials
  GET  /verification/credentials/{credential_id}
  POST /verification/credentials/revoke
  GET  /verification/subjects/{zid}/credentials
  POST /verification/attestations
  POST /verification/attestations/verify

Auth: if a token is configured, every route except /health
requires ``Authorization: Bearer <token>`` compared in
constant time. This is the seed of metered API keys.
"""
from __future__ import annotations

import base64
import hmac
import json
from http.server import BaseHTTPRequestHandler
from typing import Any, ClassVar
from urllib.parse import urlparse

from shared_engines.common.errors import EngineError
from shared_engines.common.serialization import canonical_json_dumps
from shared_engines.identity.contracts import (
    Identity,
    IdentityKind,
    IdentityStatus,
)
from shared_engines.observability.health import ComponentHealth
from shared_engines.verification.attestations import Attestation
from shared_engines.verification.credentials import (
    CredentialRecord,
    CredentialType,
)
from shared_engines.verification.media import (
    MediaKind,
    MediaRecord,
)
from shared_engines.verification.provenance import ProvenanceEvent
from shared_engines.runtime.kernel import ZyraKernel
from shared_engines.runtime.responses import (
    ApiError,
    map_engine_error,
)


class ZyraApiHandler(BaseHTTPRequestHandler):
    """Thread-safe request handler bound to a shared kernel."""

    kernel: ClassVar[ZyraKernel]

    def log_message(self, format: str, *args: object) -> None:
        return None

    def do_GET(self) -> None:
        self._dispatch("GET")

    def do_POST(self) -> None:
        self._dispatch("POST")

    def _dispatch(self, method: str) -> None:
        try:
            self._route(method)
        except ApiError as exc:
            self._send_json(exc.status, self._error_body(exc))
        except EngineError as exc:
            mapped = map_engine_error(exc)
            self._send_json(
                mapped.status, self._error_body(mapped)
            )
        except Exception:
            self._send_json(
                500,
                {
                    "ok": False,
                    "error": {
                        "type": "internal_error",
                        "message": "internal error",
                    },
                },
            )

    def _route(self, method: str) -> None:
        path = urlparse(self.path).path
        segments = [s for s in path.split("/") if s]
        if segments == ["health"] and method == "GET":
            self._handle_health()
            return
        if not self._authorized():
            raise ApiError(
                401,
                "unauthorized",
                "valid bearer token required",
            )
        if method == "GET":
            self._route_get(segments)
        elif method == "POST":
            self._route_post(segments)
        else:
            raise ApiError(
                405, "method_not_allowed", "unsupported method"
            )

    def _route_get(self, s: list[str]) -> None:
        if len(s) == 2 and s[0] == "identity":
            self._handle_get_identity(s[1])
        elif (
            len(s) == 3
            and s[0] == "verification"
            and s[1] == "media"
        ):
            self._handle_get_media(s[2])
        elif (
            len(s) == 4
            and s[0] == "verification"
            and s[1] == "media"
            and s[3] == "history"
        ):
            self._handle_media_history(s[2])
        elif (
            len(s) == 3
            and s[0] == "verification"
            and s[1] == "credentials"
        ):
            self._handle_get_credential(s[2])
        elif (
            len(s) == 4
            and s[0] == "verification"
            and s[1] == "subjects"
            and s[3] == "credentials"
        ):
            self._handle_subject_credentials(s[2])
        else:
            raise ApiError(404, "not_found", "unknown route")

    def _route_post(self, s: list[str]) -> None:
        if s == ["identity", "register"]:
            self._handle_register_identity()
        elif s == ["identity", "transition"]:
            self._handle_transition()
        elif s == ["verification", "media"]:
            self._handle_register_media()
        elif s == ["verification", "media", "verify"]:
            self._handle_verify_media()
        elif s == ["verification", "credentials"]:
            self._handle_issue_credential()
        elif s == ["verification", "credentials", "revoke"]:
            self._handle_revoke_credential()
        elif s == ["verification", "attestations"]:
            self._handle_issue_attestation()
        elif s == ["verification", "attestations", "verify"]:
            self._handle_verify_attestation()
        else:
            raise ApiError(404, "not_found", "unknown route")

    def _authorized(self) -> bool:
        token = type(self).kernel.config.api_token
        if token is None:
            return True
        header = self.headers.get("Authorization")
        if header is None:
            return False
        return hmac.compare_digest(header, f"Bearer {token}")

    def _read_json(self) -> dict[str, Any]:
        length_header = self.headers.get("Content-Length")
        if length_header is None:
            raise ApiError(
                411, "length_required", "Content-Length required"
            )
        try:
            length = int(length_header)
        except ValueError as exc:
            raise ApiError(
                400, "invalid_request", "bad Content-Length"
            ) from exc
        max_body = type(self).kernel.config.max_body_bytes
        if length > max_body:
            raise ApiError(
                413, "payload_too_large", "body exceeds limit"
            )
        raw = self.rfile.read(length)
        try:
            doc: Any = json.loads(raw.decode("utf-8"))
        except (UnicodeDecodeError, ValueError) as exc:
            raise ApiError(
                400, "invalid_json", "body is not valid JSON"
            ) from exc
        if not isinstance(doc, dict):
            raise ApiError(
                400, "invalid_request", "body must be a JSON object"
            )
        typed: dict[str, Any] = {}
        for key, value in doc.items():
            typed[str(key)] = value
        return typed

    @staticmethod
    def _require_str(doc: dict[str, Any], key: str) -> str:
        value = doc.get(key)
        if not isinstance(value, str) or not value.strip():
            raise ApiError(
                400, "invalid_request", f"missing field: {key}"
            )
        return value

    @staticmethod
    def _require_optional_str(
        doc: dict[str, Any], key: str
    ) -> str | None:
        value = doc.get(key)
        if value is None:
            return None
        if not isinstance(value, str) or not value.strip():
            raise ApiError(
                400, "invalid_request", f"invalid field: {key}"
            )
        return value

    def _send_json(
        self, status: int, payload: dict[str, Any]
    ) -> None:
        body = canonical_json_dumps(payload).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    @staticmethod
    def _error_body(exc: ApiError) -> dict[str, Any]:
        return {
            "ok": False,
            "error": {"type": exc.code, "message": exc.message},
        }

    def _ok(self, data: Any, status: int = 200) -> None:
        self._send_json(status, {"ok": True, "data": data})

    def _handle_health(self) -> None:
        kernel = type(self).kernel
        self._ok(
            {
                "overall": _health_json(kernel.health()),
                "components": [
                    _health_json(c)
                    for c in kernel.health_components()
                ],
            }
        )

    def _handle_register_identity(self) -> None:
        doc = self._read_json()
        kind_raw = self._require_str(doc, "kind")
        try:
            kind = IdentityKind(kind_raw)
        except ValueError as exc:
            raise ApiError(
                400, "invalid_request", "unknown kind"
            ) from exc
        identity = type(self).kernel.identity.register_identity(
            kind=kind,
            display_name=self._require_str(doc, "display_name"),
            actor=self._require_str(doc, "actor"),
        )
        self._ok(_identity_json(identity), status=201)

    def _handle_get_identity(self, zid: str) -> None:
        identity = type(self).kernel.identity.get_identity(zid)
        if identity is None:
            raise ApiError(
                404, "not_found", f"unknown zid: {zid}"
            )
        self._ok(_identity_json(identity))

    def _handle_transition(self) -> None:
        doc = self._read_json()
        zid = self._require_str(doc, "zid")
        try:
            target = IdentityStatus(
                self._require_str(doc, "to_status")
            )
        except ValueError as exc:
            raise ApiError(
                400, "invalid_request", "unknown to_status"
            ) from exc
        identity = type(self).kernel.identity.transition_identity(
            zid,
            target,
            actor=self._require_str(doc, "actor"),
            reason=self._require_str(doc, "reason"),
        )
        self._ok(_identity_json(identity))

    def _handle_register_media(self) -> None:
        doc = self._read_json()
        kind_raw = self._require_str(doc, "kind")
        try:
            kind = MediaKind(kind_raw)
        except ValueError as exc:
            raise ApiError(
                400, "invalid_request", "unknown media kind"
            ) from exc
        content = self._decode_b64(
            self._require_str(doc, "content_b64")
        )
        record = type(self).kernel.verification.register_media(
            owner_zid=self._require_str(doc, "owner_zid"),
            kind=kind,
            title=self._require_str(doc, "title"),
            content=content,
            content_type=self._require_str(doc, "content_type"),
            actor=self._require_str(doc, "actor"),
        )
        self._ok(_media_json(record), status=201)

    def _handle_verify_media(self) -> None:
        doc = self._read_json()
        content = self._decode_b64(
            self._require_str(doc, "content_b64")
        )
        record = type(self).kernel.verification.verify_media(
            self._require_str(doc, "media_id"), content
        )
        self._ok(_media_json(record))

    def _handle_get_media(self, media_id: str) -> None:
        record = type(self).kernel.verification.get_media(media_id)
        if record is None:
            raise ApiError(
                404, "not_found", f"unknown media: {media_id}"
            )
        self._ok(_media_json(record))

    def _handle_media_history(self, media_id: str) -> None:
        history = (
            type(self).kernel.verification.media_history(media_id)
        )
        self._ok([_provenance_json(e) for e in history])

    def _handle_issue_credential(self) -> None:
        doc = self._read_json()
        type_raw = self._require_str(doc, "credential_type")
        try:
            credential_type = CredentialType(type_raw)
        except ValueError as exc:
            raise ApiError(
                400, "invalid_request", "unknown credential_type"
            ) from exc
        record = type(self).kernel.verification.issue_credential(
            subject_zid=self._require_str(doc, "subject_zid"),
            issuer_zid=self._require_str(doc, "issuer_zid"),
            credential_type=credential_type,
            title=self._require_str(doc, "title"),
            detail=self._require_str(doc, "detail"),
        )
        self._ok(_credential_json(record), status=201)

    def _handle_get_credential(self, credential_id: str) -> None:
        record = type(self).kernel.verification.get_credential(
            credential_id
        )
        if record is None:
            raise ApiError(
                404,
                "not_found",
                f"unknown credential: {credential_id}",
            )
        self._ok(_credential_json(record))

    def _handle_revoke_credential(self) -> None:
        doc = self._read_json()
        record = type(self).kernel.verification.revoke_credential(
            self._require_str(doc, "credential_id"),
            revoked_by=self._require_str(doc, "revoked_by"),
            reason=self._require_str(doc, "reason"),
        )
        self._ok(_credential_json(record))

    def _handle_subject_credentials(self, zid: str) -> None:
        history = (
            type(self).kernel.verification.subject_history(zid)
        )
        self._ok([_credential_json(c) for c in history])

    def _handle_issue_attestation(self) -> None:
        doc = self._read_json()
        attestation = (
            type(self).kernel.verification.issue_attestation(
                subject_zid=self._require_str(doc, "subject_zid"),
                claim=self._require_str(doc, "claim"),
                subject_sha256=self._require_optional_str(
                    doc, "subject_sha256"
                ),
            )
        )
        self._ok(_attestation_json(attestation), status=201)

    def _handle_verify_attestation(self) -> None:
        doc = self._read_json()
        ok = type(self).kernel.verification.verify_attestation(
            self._require_str(doc, "attestation_id")
        )
        self._ok({"valid": ok})

    @staticmethod
    def _decode_b64(value: str) -> bytes:
        try:
            return base64.b64decode(value, validate=True)
        except ValueError as exc:
            raise ApiError(
                400,
                "invalid_request",
                "content_b64 is not valid base64",
            ) from exc


def _health_json(component: ComponentHealth) -> dict[str, object]:
    return {
        "component": component.component,
        "status": component.status.value,
        "detail": component.detail,
    }


def _identity_json(identity: Identity) -> dict[str, object]:
    return {
        "zid": identity.zid,
        "kind": identity.kind.value,
        "status": identity.status.value,
        "display_name": identity.display_name,
        "created_at": identity.created_at,
        "updated_at": identity.updated_at,
        "contract_version": identity.contract_version,
    }


def _media_json(record: MediaRecord) -> dict[str, object]:
    return {
        "media_id": record.media_id,
        "owner_zid": record.owner_zid,
        "kind": record.kind.value,
        "title": record.title,
        "content_sha256": record.content_sha256,
        "content_size": record.content_size,
        "content_type": record.content_type,
        "created_at": record.created_at,
        "contract_version": record.contract_version,
    }


def _provenance_json(event: ProvenanceEvent) -> dict[str, object]:
    return {
        "sequence": event.sequence,
        "media_id": event.media_id,
        "actor_zid": event.actor_zid,
        "action": event.action,
        "detail": event.detail,
        "occurred_at": event.occurred_at,
        "previous_hash": event.previous_hash,
        "event_hash": event.event_hash,
    }


def _credential_json(record: CredentialRecord) -> dict[str, object]:
    return {
        "credential_id": record.credential_id,
        "subject_zid": record.subject_zid,
        "issuer_zid": record.issuer_zid,
        "credential_type": record.credential_type.value,
        "title": record.title,
        "detail": record.detail,
        "issued_at": record.issued_at,
        "valid_from": record.valid_from,
        "valid_until": record.valid_until,
        "revoked": record.revoked,
        "revoked_at": record.revoked_at,
        "revoked_reason": record.revoked_reason,
        "contract_version": record.contract_version,
    }


def _attestation_json(attestation: Attestation) -> dict[str, object]:
    return {
        "attestation_id": attestation.attestation_id,
        "subject_zid": attestation.subject_zid,
        "claim": attestation.claim,
        "subject_sha256": attestation.subject_sha256,
        "issued_at": attestation.issued_at,
        "signature_b64": base64.b64encode(
            attestation.signature
        ).decode("ascii"),
        "signer_public_pem": attestation.signer_public_pem.decode(
            "utf-8"
        ),
        "contract_version": attestation.contract_version,
    }
