"""Verification engine: the public facade of the capability.

Media fingerprints detect tampering inside the Network.
Provenance chains prove custody per media item. Credential
history lets banks, employers and institutions issue
verifiable records about their clients/employees.
Attestations are portable signed statements that third
parties verify offline. AI-content detection requires real
models and arrives as a dedicated engine; this facade does
not fake it.
"""
from __future__ import annotations

from shared_engines.audit.chain import AuditTrail
from shared_engines.common.clocks import Clock
from shared_engines.common.errors import PolicyViolation
from shared_engines.events.contracts import EventCatalog
from shared_engines.events.outbox import Outbox
from shared_engines.identity.contracts import IdentityStatus
from shared_engines.identity.engine import IdentityEngine
from shared_engines.observability.backend import (
    MetricsBackend,
    NoopMetrics,
    engine_logger,
)
from shared_engines.observability.health import (
    ComponentHealth,
    HealthStatus,
)
from shared_engines.storage.database import Database
from shared_engines.verification.attestations import (
    Attestation,
    AttestationIssuer,
)
from shared_engines.verification.credentials import (
    CredentialRecord,
    CredentialRegistry,
    CredentialType,
)
from shared_engines.verification.errors import (
    AttestationNotFoundError,
    MediaNotFoundError,
)
from shared_engines.verification.media import (
    MediaKind,
    MediaPage,
    MediaRecord,
    MediaRegistry,
)
from shared_engines.verification.provenance import (
    ProvenanceChain,
    ProvenanceEvent,
)
from shared_engines.verification.signatures import (
    Ed25519Signer,
    Ed25519Verifier,
)


class VerificationEngine:
    def __init__(
        self,
        *,
        db: Database,
        clock: Clock,
        signer: Ed25519Signer,
        audit: AuditTrail,
        outbox: Outbox,
        catalog: EventCatalog,
        identity: IdentityEngine,
        metrics: MetricsBackend | None = None,
    ) -> None:
        self._db = db
        self._clock = clock
        self._signer = signer
        self._audit = audit
        self._identity = identity
        self._media = MediaRegistry(
            db=db,
            clock=clock,
            audit=audit,
            outbox=outbox,
            catalog=catalog,
        )
        self._provenance = ProvenanceChain(db=db, clock=clock)
        self._credentials = CredentialRegistry(
            db=db,
            clock=clock,
            audit=audit,
            outbox=outbox,
            catalog=catalog,
        )
        self._attestations = AttestationIssuer(
            db=db,
            clock=clock,
            signer=signer,
            audit=audit,
            outbox=outbox,
            catalog=catalog,
        )
        self._metrics = metrics if metrics is not None else NoopMetrics()
        self._log = engine_logger("verification")

    def register_media(
        self,
        *,
        owner_zid: str,
        kind: MediaKind,
        title: str,
        content: bytes,
        content_type: str,
        actor: str,
    ) -> MediaRecord:
        self._identity.require_identity(owner_zid)
        record = self._media.register(
            owner_zid=owner_zid,
            kind=kind,
            title=title,
            content=content,
            content_type=content_type,
            actor=actor,
        )
        self._provenance.record(
            media_id=record.media_id,
            actor_zid=actor,
            action="registered",
            detail=f"kind={kind.value} title={title}",
        )
        self._metrics.increment(
            "verification.media.registered",
            tags={"kind": kind.value},
        )
        self._log.info("registered media=%s", record.media_id)
        return record

    def verify_media(
        self, media_id: str, content: bytes
    ) -> MediaRecord:
        record = self._media.verify_content(media_id, content)
        self._provenance.record(
            media_id=media_id,
            actor_zid="verification-engine",
            action="verified",
            detail="content matches registry",
        )
        self._metrics.increment(
            "verification.media.verified"
        )
        self._log.info("verified media=%s", media_id)
        return record

    def get_media(self, media_id: str) -> MediaRecord | None:
        return self._media.get(media_id)

    def list_media(
        self,
        owner_zid: str,
        *,
        offset: int = 0,
        limit: int = 50,
    ) -> MediaPage:
        return self._media.list_by_owner(
            owner_zid, offset=offset, limit=limit
        )

    def media_history(
        self, media_id: str
    ) -> tuple[ProvenanceEvent, ...]:
        if self._media.get(media_id) is None:
            raise MediaNotFoundError(
                f"unknown media: {media_id}"
            )
        return self._provenance.history(media_id)

    def verify_media_history(self, media_id: str) -> bool:
        if self._media.get(media_id) is None:
            raise MediaNotFoundError(
                f"unknown media: {media_id}"
            )
        return self._provenance.verify_history(media_id)

    def issue_credential(
        self,
        *,
        subject_zid: str,
        issuer_zid: str,
        credential_type: CredentialType,
        title: str,
        detail: str,
        valid_from: float | None = None,
        valid_until: float | None = None,
    ) -> CredentialRecord:
        self._identity.require_identity(subject_zid)
        self._identity.require_identity(issuer_zid)
        issuer = self._identity.require_identity(issuer_zid)
        if issuer.status is not IdentityStatus.ACTIVE:
            raise PolicyViolation(
                f"issuer {issuer_zid} is not ACTIVE"
                f" (status={issuer.status.value})"
            )
        record = self._credentials.issue(
            subject_zid=subject_zid,
            issuer_zid=issuer_zid,
            credential_type=credential_type,
            title=title,
            detail=detail,
            valid_from=valid_from,
            valid_until=valid_until,
        )
        self._metrics.increment(
            "verification.credential.issued",
            tags={"type": credential_type.value},
        )
        self._log.info(
            "issued credential=%s", record.credential_id
        )
        return record

    def get_credential(
        self, credential_id: str
    ) -> CredentialRecord | None:
        return self._credentials.get(credential_id)

    def require_credential(
        self, credential_id: str
    ) -> CredentialRecord:
        return self._credentials.require(credential_id)

    def revoke_credential(
        self,
        credential_id: str,
        *,
        revoked_by: str,
        reason: str,
    ) -> CredentialRecord:
        record = self._credentials.revoke(
            credential_id, revoked_by=revoked_by, reason=reason
        )
        self._metrics.increment(
            "verification.credential.revoked"
        )
        self._log.info(
            "revoked credential=%s", credential_id
        )
        return record

    def subject_history(
        self, subject_zid: str
    ) -> tuple[CredentialRecord, ...]:
        self._identity.require_identity(subject_zid)
        return self._credentials.list_by_subject(subject_zid)

    def issuer_history(
        self, issuer_zid: str
    ) -> tuple[CredentialRecord, ...]:
        return self._credentials.list_by_issuer(issuer_zid)

    def issue_attestation(
        self,
        *,
        subject_zid: str,
        claim: str,
        subject_sha256: str | None = None,
    ) -> Attestation:
        self._identity.require_identity(subject_zid)
        attestation = self._attestations.issue(
            subject_zid=subject_zid,
            claim=claim,
            subject_sha256=subject_sha256,
        )
        self._metrics.increment(
            "verification.attestation.issued"
        )
        self._log.info(
            "issued attestation=%s", attestation.attestation_id
        )
        return attestation

    def require_attestation(self, attestation_id: str) -> Attestation:
        stored = self._attestations.get(attestation_id)
        if stored is None:
            raise AttestationNotFoundError(
                f"unknown attestation: {attestation_id}"
            )
        return stored

    def list_attestations(
        self, subject_zid: str
    ) -> tuple[Attestation, ...]:
        return self._attestations.list_by_subject(subject_zid)

    def verify_attestation(self, attestation_id: str) -> bool:
        stored = self._attestations.get(attestation_id)
        if stored is None:
            raise AttestationNotFoundError(
                f"unknown attestation: {attestation_id}"
            )
        ok = AttestationIssuer.verify(stored)
        self._metrics.increment(
            "verification.attestation.verified",
            tags={"result": "ok" if ok else "bad"},
        )
        self._log.info(
            "attestation verified id=%s ok=%s",
            attestation_id,
            ok,
        )
        return ok

    def check_health(self) -> ComponentHealth:
        if not self._db.ping():
            return ComponentHealth(
                "verification",
                HealthStatus.UNHEALTHY,
                "storage unavailable",
            )
        probe = b"verification-health-probe"
        try:
            signature = self._signer.sign(probe)
            ok = Ed25519Verifier(
                self._signer.public_pem
            ).verify(probe, signature)
        except Exception:
            return ComponentHealth(
                "verification",
                HealthStatus.UNHEALTHY,
                "signer self-test failed",
            )
        status = (
            HealthStatus.HEALTHY if ok else HealthStatus.UNHEALTHY
        )
        return ComponentHealth(
            "verification", status, "storage + signer ok"
        )
