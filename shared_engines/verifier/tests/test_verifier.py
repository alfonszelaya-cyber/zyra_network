from __future__ import annotations

import base64
import json
from pathlib import Path

from shared_engines.audit.chain import AuditTrail
from shared_engines.common.clocks import FrozenClock
from shared_engines.events.contracts import EventCatalog
from shared_engines.events.outbox import Outbox
from shared_engines.identity.contracts import IdentityKind
from shared_engines.identity.engine import IdentityEngine
from shared_engines.storage.database import SQLiteAdapter
from shared_engines.verification.attestations import AttestationIssuer
from shared_engines.verification.signatures import Ed25519Signer
from shared_engines.verifier.verifier import verify_attestation_blob


def _issue_attestation_json(tmp_path: Path) -> str:
    db = SQLiteAdapter(tmp_path / "v.db")
    clock = FrozenClock()
    audit = AuditTrail(db, clock)
    outbox = Outbox(db, clock)
    outbox.ensure_schema()
    catalog = EventCatalog()
    catalog.register("verification.attestation.issued")
    catalog.register("identity.registered")
    catalog.register("identity.status_changed")
    identity = IdentityEngine(
        db=db,
        clock=clock,
        audit=audit,
        outbox=outbox,
        catalog=catalog,
    )
    subject = identity.register_identity(
        kind=IdentityKind.PERSON,
        display_name="Public Figure",
        actor="registrar",
    )
    signer, _ = Ed25519Signer.generate()
    issuer = AttestationIssuer(
        db=db,
        clock=clock,
        signer=signer,
        audit=audit,
        outbox=outbox,
        catalog=catalog,
    )
    attestation = issuer.issue(
        subject_zid=subject.zid,
        claim="identity_active",
    )
    db.close()
    return json.dumps(
        {
            "format": "zyra.attestation.v1",
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
        }
    )


def test_authentic_attestation_verifies(tmp_path: Path) -> None:
    blob = _issue_attestation_json(tmp_path)
    report = verify_attestation_blob(blob)
    assert report.valid is True
    assert "AUTHENTIC" in report.reason
    assert report.attestation_id is not None
    assert report.key_fingerprint is not None
    assert len(report.key_fingerprint) == 16


def test_tampered_claim_fails(tmp_path: Path) -> None:
    blob = _issue_attestation_json(tmp_path)
    doc = json.loads(blob)
    doc["claim"] = "forged_claim"
    report = verify_attestation_blob(json.dumps(doc))
    assert report.valid is False
    assert "INVALID" in report.reason


def test_wrong_key_fails(tmp_path: Path) -> None:
    blob = _issue_attestation_json(tmp_path)
    doc = json.loads(blob)
    impostor, _ = Ed25519Signer.generate()
    doc["signer_public_pem"] = impostor.public_pem.decode("utf-8")
    report = verify_attestation_blob(json.dumps(doc))
    assert report.valid is False
    assert "INVALID" in report.reason


def test_garbage_input_fails_gracefully() -> None:
    report = verify_attestation_blob("this is not json")
    assert report.valid is False
    assert "not valid JSON" in report.reason
    report2 = verify_attestation_blob('{"format": "other"}')
    assert report2.valid is False
    assert "unknown format" in report2.reason
