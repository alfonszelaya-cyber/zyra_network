"""Certification proofs: accredited issuance with
underlying credential, scope enforcement, expiry,
cascade revocation."""
from __future__ import annotations

from pathlib import Path

import pytest

from shared_engines.audit.chain import AuditTrail
from shared_engines.common.clocks import (
    FrozenClock,
)
from shared_engines.events.contracts import (
    EventCatalog,
)
from shared_engines.events.outbox import Outbox
from shared_engines.identity.contracts import (
    IdentityKind,
)
from shared_engines.identity.engine import (
    IdentityEngine,
)
from shared_engines.certification.engine import (
    CertificationEngine,
)
from shared_engines.certification.errors import (
    IssuerNotRegisteredError,
    ScopeNotAuthorizedError,
)
from shared_engines.certification.registry import (
    IssuerRegistry,
)
from shared_engines.storage.database import (
    SQLiteAdapter,
)
from shared_engines.verification.credentials import (
    CredentialRegistry,
)
from shared_engines.verification.signatures import (
    Ed25519Signer,
)


class _Net:
    def __init__(
        self, tmp_path: Path
    ) -> None:
        self.db = SQLiteAdapter(
            tmp_path / "net.db"
        )
        self.clock = FrozenClock()
        self.audit = AuditTrail(
            self.db, self.clock
        )
        self.outbox = Outbox(
            self.db, self.clock
        )
        self.outbox.ensure_schema()
        self.catalog = EventCatalog()
        for et in (
            "identity.registered",
            "identity.status_changed",
            "verification.credential"
            ".issued",
            "verification.credential"
            ".revoked",
            "certification.certificate"
            ".issued",
            "certification.certificate"
            ".revoked",
        ):
            self.catalog.register(et)
        self.identity = IdentityEngine(
            db=self.db,
            clock=self.clock,
            audit=self.audit,
            outbox=self.outbox,
            catalog=self.catalog,
        )
        self.credentials = (
            CredentialRegistry(
                self.db,
                self.clock,
                self.audit,
                self.outbox,
                self.catalog,
            )
        )
        self.issuers = IssuerRegistry(
            self.db, self.clock
        )
        signer, _ = (
            Ed25519Signer.generate()
        )
        self.certification = (
            CertificationEngine(
                self.db,
                self.clock,
                issuers=self.issuers,
                identity=self.identity,
                credentials=(
                    self.credentials
                ),
                signer=signer,
                audit=self.audit,
                outbox=self.outbox,
            )
        )

    def close(self) -> None:
        self.db.close()


def test_accredited_issue_and_verify(
    tmp_path: Path,
) -> None:
    net = _Net(tmp_path)
    try:
        uni = (
            net.identity.register_identity(
                kind=(
                    IdentityKind
                    .INSTITUTION
                ),
                display_name="Uni SV",
                actor="bootstrap",
            )
        )
        student = (
            net.identity.register_identity(
                kind=(
                    IdentityKind.PERSON
                ),
                display_name="maria",
                actor="bootstrap",
            )
        )
        net.issuers.register_issuer(
            issuer_id=uni.zid,
            display_name="Uni SV",
            scopes=(
                "education",
                "professional",
            ),
        )
        cert = (
            net.certification
            .issue_certificate(
                subject_zid=student.zid,
                issuer_id=uni.zid,
                scope="education",
                title=(
                    "Ingenieria en"
                    " Informatica"
                ),
                detail=(
                    "Titulo registrado"
                ),
                evidence=(
                    "doc-123",
                    "record-456",
                ),
            )
        )
        assert (
            cert.credential_id != ""
        )
        underlying = (
            net.credentials.get(
                cert.credential_id
            )
        )
        assert underlying is not None
        assert (
            underlying.revoked is False
        )
        verdict = (
            net.certification
            .verify_certificate(
                certificate_id=(
                    cert.certificate_id
                )
            )
        )
        assert verdict.valid is True
        assert (
            verdict.signature_valid
            is True
        )
        assert (
            verdict.issuer_authorized
            is True
        )
        assert (
            verdict.credential_id
            == cert.credential_id
        )
    finally:
        net.close()


def test_unaccredited_or_scope_denied(
    tmp_path: Path,
) -> None:
    net = _Net(tmp_path)
    try:
        stranger = (
            net.identity.register_identity(
                kind=(
                    IdentityKind.PERSON
                ),
                display_name="x",
                actor="bootstrap",
            )
        )
        target = (
            net.identity.register_identity(
                kind=(
                    IdentityKind.PERSON
                ),
                display_name="y",
                actor="bootstrap",
            )
        )
        with pytest.raises(
            IssuerNotRegisteredError
        ):
            net.certification.issue_certificate(
                subject_zid=target.zid,
                issuer_id=stranger.zid,
                scope="education",
                title="fake",
                detail="fake",
            )
        uni = (
            net.identity.register_identity(
                kind=(
                    IdentityKind
                    .INSTITUTION
                ),
                display_name="Uni",
                actor="bootstrap",
            )
        )
        net.issuers.register_issuer(
            issuer_id=uni.zid,
            display_name="Uni",
            scopes=("education",),
        )
        with pytest.raises(
            ScopeNotAuthorizedError
        ):
            net.certification.issue_certificate(
                subject_zid=target.zid,
                issuer_id=uni.zid,
                scope="medical",
                title="fake",
                detail="fake",
            )
    finally:
        net.close()


def test_expired_certificate_invalid(
    tmp_path: Path,
) -> None:
    net = _Net(tmp_path)
    try:
        uni = (
            net.identity.register_identity(
                kind=(
                    IdentityKind
                    .INSTITUTION
                ),
                display_name="Board",
                actor="bootstrap",
            )
        )
        pro = (
            net.identity.register_identity(
                kind=(
                    IdentityKind.PERSON
                ),
                display_name="pro",
                actor="bootstrap",
            )
        )
        net.issuers.register_issuer(
            issuer_id=uni.zid,
            display_name="Board",
            scopes=(
                "professional",
            ),
        )
        cert = (
            net.certification
            .issue_certificate(
                subject_zid=pro.zid,
                issuer_id=uni.zid,
                scope="professional",
                title="Licencia",
                detail="2026",
                valid_until=(
                    net.clock.now()
                    + 10.0
                ),
            )
        )
        early = (
            net.certification
            .verify_certificate(
                certificate_id=(
                    cert.certificate_id
                )
            )
        )
        assert (
            early.within_validity
            is True
        )
        assert early.valid is True
        net.clock.advance(11)
        late = (
            net.certification
            .verify_certificate(
                certificate_id=(
                    cert.certificate_id
                )
            )
        )
        assert (
            late.within_validity
            is False
        )
        assert (
            late.valid is False
        )
    finally:
        net.close()


def test_revoke_cascades_to_credential(
    tmp_path: Path,
) -> None:
    net = _Net(tmp_path)
    try:
        uni = (
            net.identity.register_identity(
                kind=(
                    IdentityKind
                    .INSTITUTION
                ),
                display_name="Uni",
                actor="bootstrap",
            )
        )
        grad = (
            net.identity.register_identity(
                kind=(
                    IdentityKind.PERSON
                ),
                display_name="g",
                actor="bootstrap",
            )
        )
        net.issuers.register_issuer(
            issuer_id=uni.zid,
            display_name="Uni",
            scopes=("education",),
        )
        cert = (
            net.certification
            .issue_certificate(
                subject_zid=grad.zid,
                issuer_id=uni.zid,
                scope="education",
                title="Diploma",
                detail="ok",
            )
        )
        before = (
            net.certification
            .verify_certificate(
                certificate_id=(
                    cert.certificate_id
                )
            )
        )
        assert before.valid is True
        revoked = (
            net.certification
            .revoke_certificate(
                certificate_id=(
                    cert.certificate_id
                ),
                revoked_by=uni.zid,
                reason="fraud detected",
            )
        )
        assert (
            revoked.revoked is True
        )
        after = (
            net.certification
            .verify_certificate(
                certificate_id=(
                    cert.certificate_id
                )
            )
        )
        assert (
            after.valid is False
        )
        assert (
            after.not_revoked
            is False
        )
        underlying = (
            net.credentials.get(
                cert.credential_id
            )
        )
        assert underlying is not None
        assert (
            underlying.revoked is True
        )
        with pytest.raises(Exception):
            net.certification.revoke_certificate(
                certificate_id=(
                    cert.certificate_id
                ),
                revoked_by=uni.zid,
                reason="again",
            )
    finally:
        net.close()
