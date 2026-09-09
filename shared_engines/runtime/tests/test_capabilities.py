"""Capabilities proofs: the family-demo end to end
over the trust stack."""
from __future__ import annotations

from pathlib import Path

from shared_engines.audit.chain import AuditTrail
from shared_engines.common.clocks import FrozenClock
from shared_engines.events.contracts import EventCatalog
from shared_engines.events.outbox import Outbox
from shared_engines.identity.contracts import (
    IdentityKind,
    IdentityStatus,
)
from shared_engines.identity.engine import IdentityEngine
from shared_engines.network.document_exchange import (
    DocumentExchange,
)
from shared_engines.runtime.capabilities import (
    ZyraCapabilities,
)
from shared_engines.storage.database import SQLiteAdapter
from shared_engines.verification.signatures import (
    Ed25519Signer,
)


def _caps(
    tmp_path: Path,
) -> tuple[
    SQLiteAdapter,
    ZyraCapabilities,
    IdentityEngine,
]:
    db = SQLiteAdapter(tmp_path / "caps.db")
    clock = FrozenClock()
    audit = AuditTrail(db, clock)
    outbox = Outbox(db, clock)
    outbox.ensure_schema()
    catalog = EventCatalog()
    for et in (
        "identity.registered",
        "identity.status_changed",
    ):
        catalog.register(et)
    identity = IdentityEngine(
        db=db,
        clock=clock,
        audit=audit,
        outbox=outbox,
        catalog=catalog,
    )
    signer, _ = Ed25519Signer.generate()
    caps = ZyraCapabilities(
        db,
        clock,
        identity=identity,
        signer=signer,
    )
    return db, caps, identity


def test_trust_services_end_to_end(
    tmp_path: Path,
) -> None:
    db, caps, identity = _caps(tmp_path)
    try:
        caps.profiles.register_app(
            app_id="familia",
            display_name="Familia",
            scopes=(
                "display_name",
                "contact",
            ),
        )
        user = identity.register_identity(
            kind=IdentityKind.PERSON,
            display_name="maria",
            actor="familia",
        )
        caps.profiles.set_field(
            zid=user.zid,
            field="display_name",
            value="Maria Lopez",
        )
        caps.profiles.set_field(
            zid=user.zid,
            field="contact",
            value="maria@zyra.sv",
        )
        final = caps.trust.onboarding_complete(
            zid=user.zid,
            actor="verifier",
        )
        assert final.status is (
            IdentityStatus.ACTIVE
        )
        assert (
            caps.trust.is_trusted(
                zid=user.zid
            )
            is True
        )
        view = caps.profiles.view_for_app(
            app_id="familia",
            zid=user.zid,
        )
        assert (
            view.fields["display_name"]
            == "Maria Lopez"
        )
        first = caps.history.append(
            zid=user.zid,
            entry_type=(
                "birth_registration"
            ),
            actor_app="familia",
            payload={
                "hospital": "San Salvador"
            },
        )
        assert first.entry_seq == 1
        assert (
            caps.history.verify_chain(
                zid=user.zid
            )
            is True
        )
        sealed = caps.exchange.seal_document(
            owner_zid=user.zid,
            title="Acta",
            content=b"acta de nacimiento",
            actor_app="familia",
        )
        assert (
            DocumentExchange.offline_verify(
                document_id=(
                    sealed.document_id
                ),
                content=(
                    b"acta de nacimiento"
                ),
                signature=(
                    sealed.network_signature
                ),
                public_pem=(
                    sealed.public_pem
                ),
            )
            is True
        )
    finally:
        db.close()


def test_certification_search_reputation(
    tmp_path: Path,
) -> None:
    db, caps, identity = _caps(tmp_path)
    try:
        caps.profiles.register_app(
            app_id="familia",
            display_name="Familia",
            scopes=("display_name",),
        )
        uni = identity.register_identity(
            kind=IdentityKind.INSTITUTION,
            display_name="Uni SV",
            actor="familia",
        )
        user = identity.register_identity(
            kind=IdentityKind.PERSON,
            display_name="maria lopez",
            actor="familia",
        )
        caps.issuers.register_issuer(
            issuer_id=uni.zid,
            display_name="Uni SV",
            scopes=("education",),
        )
        cert = (
            caps.certification
            .issue_certificate(
                subject_zid=user.zid,
                issuer_id=uni.zid,
                scope="education",
                title=(
                    "Ingenieria"
                    " Informatica"
                ),
                detail="titulo",
            )
        )
        verdict = (
            caps.certification
            .verify_certificate(
                certificate_id=(
                    cert.certificate_id
                )
            )
        )
        assert verdict.valid is True
        result = caps.search.search(
            app_id="familia",
            query="ingenieria",
        )
        sources = {
            h.source
            for h in result.items
        }
        assert (
            "certificate" in sources
        )
        event = caps.reputation.record_event(
            subject_zid=user.zid,
            actor_zid=uni.zid,
            kind="positive",
            evidence=b"titulo verificado",
        )
        summary = caps.reputation.summary(
            subject_zid=user.zid
        )
        assert summary.score == 10
        assert (
            caps.reputation.verify_evidence(
                event_id=event.event_id,
                evidence=(
                    b"titulo verificado"
                ),
            )
            is True
        )
    finally:
        db.close()


def test_export_interop_compliance_ai_encryption(
    tmp_path: Path,
) -> None:
    db, caps, identity = _caps(tmp_path)
    try:
        caps.profiles.register_app(
            app_id="familia",
            display_name="Familia",
            scopes=("display_name",),
        )
        _ = identity
        bundle = caps.export.export_bundle(
            subject_zid="ZID-1",
            entries=(
                (
                    "doc",
                    "D-1",
                    "acta",
                ),
            ),
            actor_app="familia",
        )
        assert (
            caps.export.verify_stored(
                bundle_id=(
                    bundle.bundle_id
                )
            )
            is True
        )
        caps.interop.register_schema(
            schema_id="zyra.demo",
            version=1,
            definition="demo",
        )
        agreed = caps.interop.negotiate(
            schema_id="zyra.demo",
            client_versions=(1, 2),
        )
        assert agreed.agreed_version == 1
        caps.compliance.register_policy(
            jurisdiction="SV",
            requirement="kyc_verified",
            mandatory=True,
        )
        decision = caps.compliance.evaluate(
            subject_zid="ZID-1",
            jurisdiction="SV",
            requirement="kyc_verified",
            satisfied=True,
        )
        assert (
            decision.compliant is True
        )
        caps.ai.register_model(
            model_id="classifier",
            provider="lab",
            model_version="1.0",
            capabilities=("document",),
        )
        record = caps.ai.record_analysis(
            model_id="classifier",
            content_sha256="a" * 64,
            verdict="authentic",
            confidence=0.9,
        )
        assert (
            record.model_version
            == "1.0"
        )
        sealed = caps.encryption.seal(
            b"secreto de la familia"
        )
        assert (
            caps.encryption.open(sealed)
            == b"secreto de la familia"
        )
    finally:
        db.close()
