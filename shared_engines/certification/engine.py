"""Certification engine: the integration layer.

Composes EXISTING network capabilities into formal
certifications - never duplicating them:

    IssuerRegistry     who may certify what (new)
    IdentityEngine     subject + issuer exist (reuse)
    CredentialRegistry durable credential per
                       certificate, revocable
                       (reuse, CERTIFICATION type)
    Ed25519Signer      network-notarized signature
                       (reuse)

A certificate is a signed, durable, verifiable
statement bound to its underlying credential:
revoke certificate -> credential revoked too.
"""
from __future__ import annotations

import hashlib
import json
import sqlite3

from shared_engines.audit.chain import AuditTrail
from shared_engines.common.clocks import Clock
from shared_engines.common.errors import (
    NotFoundError,
)
from shared_engines.common.identifiers import (
    new_id,
)
from shared_engines.common.serialization import (
    canonical_json_dumps,
)
from shared_engines.common.validation import (
    require_non_empty_str,
)
from shared_engines.events.outbox import Outbox
from shared_engines.identity.engine import (
    IdentityEngine,
)
from shared_engines.certification.contracts import (
    CertificateRecord,
    CertificationVerdict,
)
from shared_engines.certification.errors import (
    AlreadyRevokedError,
    CertificateNotFoundError,
    IssuerNotRegisteredError,
    ScopeNotAuthorizedError,
)
from shared_engines.certification.registry import (
    IssuerRegistry,
)
from shared_engines.storage.database import (
    Database,
)
from shared_engines.storage.migrations import (
    Migration,
    MigrationRunner,
)
from shared_engines.verification.credentials import (
    CredentialRegistry,
    CredentialType,
)
from shared_engines.verification.signatures import (
    Ed25519Signer,
    Ed25519Verifier,
)

EVENT_CERT_ISSUED = (
    "certification.certificate.issued"
)
EVENT_CERT_REVOKED = (
    "certification.certificate.revoked"
)

_MIGRATIONS = (
    Migration(
        1,
        "certificates",
        (
            "CREATE TABLE certificates ("
            " certificate_id TEXT"
            " PRIMARY KEY,"
            " subject_zid TEXT NOT NULL,"
            " issuer_id TEXT NOT NULL,"
            " scope TEXT NOT NULL,"
            " title TEXT NOT NULL,"
            " detail TEXT NOT NULL,"
            " evidence_json TEXT"
            " NOT NULL,"
            " content_sha TEXT NOT NULL,"
            " credential_id TEXT"
            " NOT NULL,"
            " signature BLOB NOT NULL,"
            " public_pem BLOB NOT NULL,"
            " issued_at REAL NOT NULL,"
            " valid_until REAL,"
            " revoked INTEGER NOT NULL"
            " DEFAULT 0,"
            " revoked_at REAL,"
            " revoked_reason TEXT)",
            "CREATE INDEX certs_subject"
            " ON certificates"
            " (subject_zid)",
            "CREATE INDEX certs_scope"
            " ON certificates (scope)",
        ),
    ),
)


def _content_sha(
    *,
    title: str,
    detail: str,
    evidence: tuple[str, ...],
    issued_at: float,
    valid_until: float | None,
) -> str:
    src = canonical_json_dumps(
        {
            "title": title,
            "detail": detail,
            "evidence": list(evidence),
            "issued_at": issued_at,
            "valid_until": valid_until,
        }
    )
    return hashlib.sha256(
        src.encode("utf-8")
    ).hexdigest()


def _sig_payload(
    *,
    certificate_id: str,
    subject_zid: str,
    issuer_id: str,
    scope: str,
    content_sha: str,
) -> bytes:
    return (
        f"CERT:{certificate_id}:"
        f"{subject_zid}:{issuer_id}:"
        f"{scope}:{content_sha}"
    ).encode("utf-8")


class CertificationEngine:
    """Formal certifications over existing
    engines."""

    def __init__(
        self,
        db: Database,
        clock: Clock,
        *,
        issuers: IssuerRegistry,
        identity: IdentityEngine,
        credentials: CredentialRegistry,
        signer: Ed25519Signer,
        audit: AuditTrail,
        outbox: Outbox,
    ) -> None:
        self._db = db
        self._clock = clock
        self._issuers = issuers
        self._identity = identity
        self._credentials = (
            credentials
        )
        self._signer = signer
        self._audit = audit
        self._outbox = outbox
        self._public_pem = (
            signer.public_pem
        )
        MigrationRunner(
            db,
            "certification.certs",
            _MIGRATIONS,
        ).run(clock)

    def _emit(
        self,
        cursor: sqlite3.Cursor,
        *,
        event_type: str,
        aggregate: str,
        payload: dict[str, object],
    ) -> None:
        event_id = hashlib.sha256(
            canonical_json_dumps(
                {
                    "t": event_type,
                    "a": aggregate,
                    "p": payload,
                    "ts": self._clock.now(),
                }
            ).encode("utf-8")
        ).hexdigest()[:32]
        fp = hashlib.sha256(
            canonical_json_dumps(
                {
                    "id": event_id,
                    "ty": event_type,
                }
            ).encode("utf-8")
        ).hexdigest()
        cursor.execute(
            "INSERT INTO events_outbox"
            " (event_id, event_type,"
            " aggregate_id, schema_version,"
            " envelope_version, created_at,"
            " payload, fingerprint,"
            " published_at)"
            " VALUES (?, ?, ?, 1, 1, ?, ?,"
            " ?, NULL)",
            (
                event_id,
                event_type,
                aggregate,
                self._clock.now(),
                canonical_json_dumps(
                    payload
                ),
                fp,
            ),
        )

    def issue_certificate(
        self,
        *,
        subject_zid: str,
        issuer_id: str,
        scope: str,
        title: str,
        detail: str,
        evidence: tuple[str, ...] = (),
        valid_until: float | None = None,
    ) -> CertificateRecord:
        """Accredited issuer certifies a
        subject. Refuses unregistered issuers,
        unauthorized scopes, unknown subjects.
        Always creates the underlying durable
        credential (integration, not
        duplication)."""
        require_non_empty_str(
            subject_zid, "subject_zid"
        )
        require_non_empty_str(
            issuer_id, "issuer_id"
        )
        require_non_empty_str(
            scope, "scope"
        )
        require_non_empty_str(
            title, "title"
        )
        issuer = (
            self._issuers.get_issuer(
                issuer_id
            )
        )
        if issuer is None:
            raise IssuerNotRegisteredError(
                "not an accredited"
                f" certifier: {issuer_id}"
            )
        if not issuer.active:
            raise IssuerNotRegisteredError(
                "certifier deactivated:"
                f" {issuer_id}"
            )
        if scope not in issuer.scopes:
            raise ScopeNotAuthorizedError(
                f"issuer {issuer_id} is"
                " not accredited for"
                f" scope '{scope}'"
            )
        self._identity.require_identity(
            subject_zid
        )
        self._identity.require_identity(
            issuer_id
        )
        now = self._clock.now()
        credential = (
            self._credentials.issue(
                subject_zid=subject_zid,
                issuer_zid=issuer_id,
                credential_type=(
                    CredentialType
                    .CERTIFICATION
                ),
                title=title,
                detail=detail,
                valid_from=now,
                valid_until=valid_until,
            )
        )
        certificate_id = (
            f"CRT-{new_id()}"
        )
        content_sha = _content_sha(
            title=title,
            detail=detail,
            evidence=evidence,
            issued_at=now,
            valid_until=valid_until,
        )
        signature = self._signer.sign(
            _sig_payload(
                certificate_id=(
                    certificate_id
                ),
                subject_zid=subject_zid,
                issuer_id=issuer_id,
                scope=scope,
                content_sha=content_sha,
            )
        )
        with (
            self._db.transaction()
            as cursor
        ):
            cursor.execute(
                "INSERT INTO certificates"
                " (certificate_id,"
                " subject_zid, issuer_id,"
                " scope, title, detail,"
                " evidence_json,"
                " content_sha,"
                " credential_id,"
                " signature, public_pem,"
                " issued_at, valid_until)"
                " VALUES (?, ?, ?, ?, ?, ?,"
                " ?, ?, ?, ?, ?, ?, ?)",
                (
                    certificate_id,
                    subject_zid,
                    issuer_id,
                    scope,
                    title,
                    detail,
                    canonical_json_dumps(
                        list(evidence)
                    ),
                    content_sha,
                    credential.credential_id,
                    signature,
                    self._public_pem,
                    now,
                    valid_until,
                ),
            )
            self._emit(
                cursor,
                event_type=(
                    EVENT_CERT_ISSUED
                ),
                aggregate=(
                    certificate_id
                ),
                payload={
                    "subject": (
                        subject_zid
                    ),
                    "issuer": issuer_id,
                    "scope": scope,
                },
            )
        self._audit.append(
            event_type=EVENT_CERT_ISSUED,
            actor=issuer_id,
            subject=certificate_id,
            payload={
                "subject": subject_zid,
                "scope": scope,
            },
        )
        return (
            self.require_certificate(
                certificate_id=(
                    certificate_id
                )
            )
        )

    def _row_to_record(
        self, row: sqlite3.Row
    ) -> CertificateRecord:
        raw_ev = row["evidence_json"]
        parsed = json.loads(str(raw_ev))
        ev_list = (
            [str(e) for e in parsed]
            if isinstance(parsed, list)
            else []
        )
        return CertificateRecord(
            certificate_id=str(
                row["certificate_id"]
            ),
            subject_zid=str(
                row["subject_zid"]
            ),
            issuer_id=str(
                row["issuer_id"]
            ),
            scope=str(row["scope"]),
            title=str(row["title"]),
            detail=str(
                row["detail"]
            ),
            evidence=tuple(ev_list),
            credential_id=str(
                row["credential_id"]
            ),
            signature=bytes(
                row["signature"]
            ),
            public_pem=bytes(
                row["public_pem"]
            ),
            issued_at=float(
                row["issued_at"]
            ),
            valid_until=(
                float(
                    row["valid_until"]
                )
                if row["valid_until"]
                is not None
                else None
            ),
            revoked=bool(
                int(row["revoked"])
            ),
        )

    def get_certificate(
        self,
        *,
        certificate_id: str,
    ) -> CertificateRecord | None:
        row = self._db.query_one(
            "SELECT * FROM certificates"
            " WHERE certificate_id = ?",
            (certificate_id,),
        )
        if row is None:
            return None
        return self._row_to_record(
            row
        )

    def require_certificate(
        self,
        *,
        certificate_id: str,
    ) -> CertificateRecord:
        record = self.get_certificate(
            certificate_id=(
                certificate_id
            )
        )
        if record is None:
            raise (
                CertificateNotFoundError(
                    "unknown certificate:"
                    f" {certificate_id}"
                )
            )
        return record

    def verify_certificate(
        self,
        *,
        certificate_id: str,
    ) -> CertificationVerdict:
        """Full evidence-backed check:
        signature, validity window, issuer
        accreditation, revocation."""
        row = self._db.query_one(
            "SELECT * FROM certificates"
            " WHERE certificate_id = ?",
            (certificate_id,),
        )
        if row is None:
            raise NotFoundError(
                "unknown certificate:"
                f" {certificate_id}"
            )
        record = self._row_to_record(
            row
        )
        content_sha = _content_sha(
            title=record.title,
            detail=record.detail,
            evidence=record.evidence,
            issued_at=(
                record.issued_at
            ),
            valid_until=(
                record.valid_until
            ),
        )
        verifier = Ed25519Verifier(
            record.public_pem
        )
        signature_valid = (
            verifier.verify(
                _sig_payload(
                    certificate_id=(
                        certificate_id
                    ),
                    subject_zid=(
                        record.subject_zid
                    ),
                    issuer_id=(
                        record.issuer_id
                    ),
                    scope=record.scope,
                    content_sha=(
                        content_sha
                    ),
                ),
                record.signature,
            )
        )
        now = self._clock.now()
        within = (
            record.valid_until is None
            or now <= record.valid_until
        )
        authorized = (
            self._issuers.has_scope(
                issuer_id=(
                    record.issuer_id
                ),
                scope=record.scope,
            )
        )
        not_revoked = (
            not record.revoked
        )
        valid = (
            signature_valid
            and within
            and authorized
            and not_revoked
        )
        return CertificationVerdict(
            certificate_id=(
                certificate_id
            ),
            signature_valid=(
                signature_valid
            ),
            within_validity=within,
            issuer_authorized=(
                authorized
            ),
            not_revoked=not_revoked,
            valid=valid,
            credential_id=(
                record.credential_id
            ),
            evidence={
                "subject": (
                    record.subject_zid
                ),
                "issuer": (
                    record.issuer_id
                ),
                "scope": record.scope,
                "issued_at": (
                    record.issued_at
                ),
                "valid_until": (
                    record.valid_until
                ),
            },
        )

    def revoke_certificate(
        self,
        *,
        certificate_id: str,
        revoked_by: str,
        reason: str,
    ) -> CertificateRecord:
        """Revoke the certificate AND its
        underlying credential (cascade)."""
        record = (
            self.require_certificate(
                certificate_id=(
                    certificate_id
                )
            )
        )
        if record.revoked:
            raise AlreadyRevokedError(
                "already revoked:"
                f" {certificate_id}"
            )
        now = self._clock.now()
        with (
            self._db.transaction()
            as cursor
        ):
            cursor.execute(
                "UPDATE certificates"
                " SET revoked = 1,"
                " revoked_at = ?,"
                " revoked_reason = ?"
                " WHERE certificate_id"
                " = ?",
                (
                    now,
                    reason,
                    certificate_id,
                ),
            )
            self._emit(
                cursor,
                event_type=(
                    EVENT_CERT_REVOKED
                ),
                aggregate=(
                    certificate_id
                ),
                payload={
                    "reason": reason
                },
            )
        self._credentials.revoke(
            record.credential_id,
            revoked_by=revoked_by,
            reason=reason,
        )
        self._audit.append(
            event_type=(
                EVENT_CERT_REVOKED
            ),
            actor=revoked_by,
            subject=certificate_id,
            payload={"reason": reason},
        )
        return (
            self.require_certificate(
                certificate_id=(
                    certificate_id
                )
            )
        )

    def list_by_subject(
        self, *, subject_zid: str
    ) -> tuple[CertificateRecord, ...]:
        rows = self._db.query_all(
            "SELECT * FROM certificates"
            " WHERE subject_zid = ?"
            " ORDER BY issued_at",
            (subject_zid,),
        )
        return tuple(
            self._row_to_record(row)
            for row in rows
        )

    def list_by_scope(
        self, *, scope: str
    ) -> tuple[CertificateRecord, ...]:
        rows = self._db.query_all(
            "SELECT * FROM certificates"
            " WHERE scope = ?"
            " ORDER BY issued_at",
            (scope,),
        )
        return tuple(
            self._row_to_record(row)
            for row in rows
        )
