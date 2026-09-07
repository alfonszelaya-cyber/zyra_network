from __future__ import annotations

from dataclasses import replace
from pathlib import Path

import pytest

from shared_engines.audit.chain import AuditTrail
from shared_engines.common.clocks import FrozenClock
from shared_engines.common.errors import PolicyViolation
from shared_engines.events.contracts import Event, EventCatalog
from shared_engines.events.outbox import Outbox
from shared_engines.identity.contracts import (
    IdentityKind,
    IdentityStatus,
)
from shared_engines.identity.engine import IdentityEngine
from shared_engines.identity.errors import IdentityNotFoundError
from shared_engines.observability.backend import InMemoryMetrics
from shared_engines.observability.health import HealthStatus
from shared_engines.storage.database import SQLiteAdapter
from shared_engines.verification.attestations import AttestationIssuer
from shared_engines.verification.credentials import CredentialType
from shared_engines.verification.engine import VerificationEngine
from shared_engines.verification.errors import (
    AttestationNotFoundError,
    CredentialNotFoundError,
    MediaNotFoundError,
    TamperDetectedError,
)
from shared_engines.verification.media import MediaKind
from shared_engines.verification.signatures import (
    Ed25519Signer,
    Ed25519Verifier,
)


class _Harness:
    def __init__(self, tmp_path: Path) -> None:
        self.db = SQLiteAdapter(tmp_path / "verification.db")
        self.clock = FrozenClock()
        self.audit = AuditTrail(self.db, self.clock)
        self.outbox = Outbox(self.db, self.clock)
        self.outbox.ensure_schema()
        self.catalog = EventCatalog()
        for event_type in (
            "verification.media.registered",
            "verification.media.tamper_detected",
            "verification.credential.issued",
            "verification.credential.revoked",
            "verification.attestation.issued",
            "identity.registered",
            "identity.status_changed",
        ):
            self.catalog.register(event_type)
        signer, _ = Ed25519Signer.generate()
        self.identity = IdentityEngine(
            db=self.db,
            clock=self.clock,
            audit=self.audit,
            outbox=self.outbox,
            catalog=self.catalog,
        )
        self.metrics = InMemoryMetrics()
        self.engine = VerificationEngine(
            db=self.db,
            clock=self.clock,
            signer=signer,
            audit=self.audit,
            outbox=self.outbox,
            catalog=self.catalog,
            identity=self.identity,
            metrics=self.metrics,
        )

    def _activate(self, zid: str) -> None:
        self.identity.transition_identity(
            zid,
            IdentityStatus.ACTIVE,
            actor="bootstrap",
            reason="onboarded",
        )

    def active_issuer(self, name: str = "Bank A") -> str:
        issuer = self.identity.register_identity(
            kind=IdentityKind.INSTITUTION,
            display_name=name,
            actor="bootstrap",
        )
        self._activate(issuer.zid)
        return issuer.zid

    def active_subject(self, name: str = "Client A") -> str:
        subject = self.identity.register_identity(
            kind=IdentityKind.PERSON,
            display_name=name,
            actor="registrar",
        )
        self._activate(subject.zid)
        return subject.zid

    def close(self) -> None:
        self.db.close()


def test_register_photo_video_audio_document(
    tmp_path: Path,
) -> None:
    harness = _Harness(tmp_path)
    owner = harness.active_subject()
    photo = harness.engine.register_media(
        owner_zid=owner,
        kind=MediaKind.PHOTO,
        title="profile.jpg",
        content=b"\xff\xd8\xff\xe0fake-jpeg-bytes",
        content_type="image/jpeg",
        actor="clerk",
    )
    video = harness.engine.register_media(
        owner_zid=owner,
        kind=MediaKind.VIDEO,
        title="interview.mp4",
        content=b"\x00\x00\x00\x18ftypmp42fake-mp4",
        content_type="video/mp4",
        actor="clerk",
    )
    audio = harness.engine.register_media(
        owner_zid=owner,
        kind=MediaKind.AUDIO,
        title="voice.wav",
        content=b"RIFFfake-wav",
        content_type="audio/wav",
        actor="clerk",
    )
    document = harness.engine.register_media(
        owner_zid=owner,
        kind=MediaKind.DOCUMENT,
        title="contract.pdf",
        content=b"%PDF-1.4 fake-pdf",
        content_type="application/pdf",
        actor="clerk",
    )
    assert photo.kind is MediaKind.PHOTO
    assert video.kind is MediaKind.VIDEO
    assert audio.kind is MediaKind.AUDIO
    assert document.kind is MediaKind.DOCUMENT
    ids = {
        photo.media_id,
        video.media_id,
        audio.media_id,
        document.media_id,
    }
    assert len(ids) == 4
    harness.close()


def test_media_tampering_detected_for_any_kind(
    tmp_path: Path,
) -> None:
    harness = _Harness(tmp_path)
    owner = harness.active_subject()
    photo = harness.engine.register_media(
        owner_zid=owner,
        kind=MediaKind.PHOTO,
        title="original.jpg",
        content=b"original-jpeg",
        content_type="image/jpeg",
        actor="clerk",
    )
    with pytest.raises(TamperDetectedError):
        harness.engine.verify_media(
            photo.media_id, b"photoshopped-jpeg"
        )
    video = harness.engine.register_media(
        owner_zid=owner,
        kind=MediaKind.VIDEO,
        title="original.mp4",
        content=b"original-mp4",
        content_type="video/mp4",
        actor="clerk",
    )
    with pytest.raises(TamperDetectedError):
        harness.engine.verify_media(
            video.media_id, b"deepfake-mp4"
        )
    harness.close()


def test_media_history_chain_verifiable(tmp_path: Path) -> None:
    harness = _Harness(tmp_path)
    owner = harness.active_subject()
    media = harness.engine.register_media(
        owner_zid=owner,
        kind=MediaKind.PHOTO,
        title="evidence.jpg",
        content=b"evidence-bytes",
        content_type="image/jpeg",
        actor="uploader-1",
    )
    harness.engine.verify_media(media.media_id, b"evidence-bytes")
    history = harness.engine.media_history(media.media_id)
    assert len(history) == 2
    assert history[0].action == "registered"
    assert history[1].action == "verified"
    assert harness.engine.verify_media_history(media.media_id)
    harness.close()


def test_credential_history_for_bank_client(
    tmp_path: Path,
) -> None:
    harness = _Harness(tmp_path)
    bank = harness.active_issuer("Global Bank")
    client = harness.active_subject("Client X")
    harness.engine.issue_credential(
        subject_zid=client,
        issuer_zid=bank,
        credential_type=CredentialType.KYC_VERIFIED,
        title="KYC completed",
        detail="Identity verified in person",
    )
    harness.engine.issue_credential(
        subject_zid=client,
        issuer_zid=bank,
        credential_type=CredentialType.FINANCIAL,
        title="Active account",
        detail="Checking account active since 2020",
    )
    employer = harness.active_issuer("Tech Corp")
    harness.engine.issue_credential(
        subject_zid=client,
        issuer_zid=employer,
        credential_type=CredentialType.EMPLOYMENT,
        title="Senior Engineer",
        detail="Employed from 2021 to present",
    )
    history = harness.engine.subject_history(client)
    assert len(history) == 3
    types = {c.credential_type for c in history}
    assert types == {
        CredentialType.KYC_VERIFIED,
        CredentialType.FINANCIAL,
        CredentialType.EMPLOYMENT,
    }
    issuers = {c.issuer_zid for c in history}
    assert issuers == {bank, employer}
    assert all(not c.revoked for c in history)
    harness.close()


def test_credential_revocation_is_explicit(
    tmp_path: Path,
) -> None:
    harness = _Harness(tmp_path)
    issuer = harness.active_issuer("Cert Body")
    subject = harness.active_subject("Certified Person")
    credential = harness.engine.issue_credential(
        subject_zid=subject,
        issuer_zid=issuer,
        credential_type=CredentialType.CERTIFICATION,
        title="ISO 27001 Auditor",
        detail="Valid for 3 years",
    )
    assert not credential.revoked
    revoked = harness.engine.revoke_credential(
        credential.credential_id,
        revoked_by=issuer,
        reason="Misconduct detected",
    )
    assert revoked.revoked
    assert revoked.revoked_reason == "Misconduct detected"
    history = harness.engine.subject_history(subject)
    assert len(history) == 1
    assert history[0].revoked
    harness.close()


def test_issuer_must_be_active(tmp_path: Path) -> None:
    harness = _Harness(tmp_path)
    dormant_issuer = harness.identity.register_identity(
        kind=IdentityKind.INSTITUTION,
        display_name="Not Yet Active Corp",
        actor="bootstrap",
    )
    subject = harness.active_subject("Client Y")
    with pytest.raises(PolicyViolation):
        harness.engine.issue_credential(
            subject_zid=subject,
            issuer_zid=dormant_issuer.zid,
            credential_type=CredentialType.REFERENCE,
            title="Ref",
            detail="Should fail: issuer not ACTIVE",
        )
    harness.close()


def test_subject_must_exist(tmp_path: Path) -> None:
    harness = _Harness(tmp_path)
    issuer = harness.active_issuer()
    with pytest.raises(IdentityNotFoundError):
        harness.engine.issue_credential(
            subject_zid="ZID-ghost",
            issuer_zid=issuer,
            credential_type=CredentialType.REFERENCE,
            title="x",
            detail="y",
        )
    harness.close()


def test_credential_not_found(tmp_path: Path) -> None:
    harness = _Harness(tmp_path)
    with pytest.raises(CredentialNotFoundError):
        harness.engine.require_credential("CRD-missing")
    with pytest.raises(CredentialNotFoundError):
        harness.engine.revoke_credential(
            "CRD-missing",
            revoked_by="anyone",
            reason="no reason",
        )
    harness.close()


def test_attestation_third_party_verifiable(
    tmp_path: Path,
) -> None:
    harness = _Harness(tmp_path)
    subject = harness.active_subject()
    attestation = harness.engine.issue_attestation(
        subject_zid=subject,
        claim="identity_active",
    )
    assert AttestationIssuer.verify(attestation) is True
    forged = replace(attestation, claim="forged")
    assert AttestationIssuer.verify(forged) is False
    assert (
        harness.engine.verify_attestation(
            attestation.attestation_id
        )
        is True
    )
    harness.close()


def test_attestation_binds_media_content(
    tmp_path: Path,
) -> None:
    harness = _Harness(tmp_path)
    owner = harness.active_subject()
    media = harness.engine.register_media(
        owner_zid=owner,
        kind=MediaKind.DOCUMENT,
        title="title-deed.pdf",
        content=b"title-deed-content",
        content_type="application/pdf",
        actor="clerk",
    )
    attestation = harness.engine.issue_attestation(
        subject_zid=owner,
        claim="document_is_authentic",
        subject_sha256=media.content_sha256,
    )
    assert attestation.subject_sha256 == media.content_sha256
    assert AttestationIssuer.verify(attestation) is True
    forged = replace(
        attestation, subject_sha256="0" * 64
    )
    assert AttestationIssuer.verify(forged) is False
    harness.close()


def test_unknown_media_and_attestation_raise(
    tmp_path: Path,
) -> None:
    harness = _Harness(tmp_path)
    with pytest.raises(MediaNotFoundError):
        harness.engine.verify_media("MED-missing", b"x")
    with pytest.raises(MediaNotFoundError):
        harness.engine.media_history("MED-missing")
    with pytest.raises(AttestationNotFoundError):
        harness.engine.require_attestation("ATT-missing")
    with pytest.raises(AttestationNotFoundError):
        harness.engine.verify_attestation("ATT-missing")
    harness.close()


def test_media_pagination_by_owner(tmp_path: Path) -> None:
    harness = _Harness(tmp_path)
    owner = harness.active_subject()
    for index in range(5):
        harness.engine.register_media(
            owner_zid=owner,
            kind=MediaKind.PHOTO,
            title=f"photo-{index}.jpg",
            content=f"content-{index}".encode("utf-8"),
            content_type="image/jpeg",
            actor="clerk",
        )
    page1 = harness.engine.list_media(
        owner, offset=0, limit=3
    )
    assert page1.total == 5
    assert len(page1.items) == 3
    assert page1.has_more
    page2 = harness.engine.list_media(
        owner, offset=3, limit=3
    )
    assert len(page2.items) == 2
    assert not page2.has_more
    harness.close()


def test_audit_chain_intact_after_full_flow(
    tmp_path: Path,
) -> None:
    harness = _Harness(tmp_path)
    issuer = harness.active_issuer("Bank Z")
    subject = harness.active_subject("Person Q")
    media = harness.engine.register_media(
        owner_zid=subject,
        kind=MediaKind.DOCUMENT,
        title="statement.pdf",
        content=b"statement",
        content_type="application/pdf",
        actor="clerk",
    )
    harness.engine.issue_credential(
        subject_zid=subject,
        issuer_zid=issuer,
        credential_type=CredentialType.FINANCIAL,
        title="Statement issued",
        detail=f"See media {media.media_id}",
    )
    harness.engine.issue_attestation(
        subject_zid=subject,
        claim="kyc_complete",
    )
    with pytest.raises(TamperDetectedError):
        harness.engine.verify_media(media.media_id, b"wrong")
    assert harness.audit.verify() > 0
    harness.close()


def test_outbox_events_from_full_flow(tmp_path: Path) -> None:
    harness = _Harness(tmp_path)
    issuer = harness.active_issuer()
    subject = harness.active_subject()
    harness.engine.register_media(
        owner_zid=subject,
        kind=MediaKind.PHOTO,
        title="a.jpg",
        content=b"aa",
        content_type="image/jpeg",
        actor="clerk",
    )
    harness.engine.issue_credential(
        subject_zid=subject,
        issuer_zid=issuer,
        credential_type=CredentialType.KYC_VERIFIED,
        title="KYC",
        detail="verified",
    )
    harness.engine.issue_attestation(
        subject_zid=subject,
        claim="c",
    )
    collected: list[Event] = []

    def collect(event: Event) -> None:
        collected.append(event)

    harness.outbox.dispatch_pending(collect)
    by_type = {event.event_type for event in collected}
    assert by_type >= {
        "verification.media.registered",
        "verification.credential.issued",
        "verification.attestation.issued",
    }
    harness.close()


def test_health_healthy_then_unhealthy(tmp_path: Path) -> None:
    harness = _Harness(tmp_path)
    assert (
        harness.engine.check_health().status
        is HealthStatus.HEALTHY
    )
    harness.db.close()
    assert (
        harness.engine.check_health().status
        is HealthStatus.UNHEALTHY
    )


def test_signature_rejects_wrong_key_and_tampered_data() -> None:
    signer, _private_pem = Ed25519Signer.generate()
    verifier = Ed25519Verifier(signer.public_pem)
    data = b"authentic"
    signature = signer.sign(data)
    assert verifier.verify(data, signature)
    assert not verifier.verify(b"tampered", signature)
    other_signer, _ = Ed25519Signer.generate()
    other_verifier = Ed25519Verifier(other_signer.public_pem)
    assert not other_verifier.verify(data, signature)
