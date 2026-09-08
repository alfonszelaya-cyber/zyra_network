"""Offline attestation verification: paste, verify, trust.

Anyone holding an attestation JSON (signature + public key
embedded) verifies it WITHOUT database access. This is the
public face of the Network's trust: provable, not promised.
"""
from __future__ import annotations

import base64
import hashlib
from dataclasses import dataclass

from shared_engines.common.serialization import (
    canonical_json_dumps,
    canonical_json_loads,
)
from shared_engines.verification.signatures import Ed25519Verifier

ATTESTATION_FORMAT = "zyra.attestation.v1"


@dataclass(frozen=True)
class VerificationReport:
    valid: bool
    reason: str
    attestation_id: str | None
    subject_zid: str | None
    claim: str | None
    issued_at: float | None
    key_fingerprint: str | None


def _key_fingerprint(public_pem: bytes) -> str:
    return hashlib.sha256(public_pem).hexdigest()[:16]


def _fail(reason: str) -> VerificationReport:
    return VerificationReport(
        valid=False,
        reason=reason,
        attestation_id=None,
        subject_zid=None,
        claim=None,
        issued_at=None,
        key_fingerprint=None,
    )


def verify_attestation_blob(blob: str) -> VerificationReport:
    """Verifies a pasted attestation JSON, fully offline."""
    try:
        doc = canonical_json_loads(blob)
    except Exception:
        return _fail("the pasted text is not valid JSON")
    if not isinstance(doc, dict):
        return _fail("attestation must be a JSON object")
    if doc.get("format") != ATTESTATION_FORMAT:
        return _fail(
            f"unknown format (expected {ATTESTATION_FORMAT})"
        )
    required = (
        "attestation_id",
        "subject_zid",
        "claim",
        "issued_at",
        "signature_b64",
        "signer_public_pem",
    )
    missing = [k for k in required if k not in doc]
    if missing:
        return _fail(f"missing fields: {', '.join(missing)}")
    try:
        signature = base64.b64decode(
            str(doc["signature_b64"]), validate=True
        )
        public_pem = str(doc["signer_public_pem"]).encode("utf-8")
        issued_at = float(doc["issued_at"])
    except Exception:
        return _fail("signature, key or timestamp is malformed")
    subject_sha256 = doc.get("subject_sha256")
    payload = {
        "format": ATTESTATION_FORMAT,
        "attestation_id": str(doc["attestation_id"]),
        "subject_zid": str(doc["subject_zid"]),
        "claim": str(doc["claim"]),
        "subject_sha256": (
            None
            if subject_sha256 is None
            else str(subject_sha256)
        ),
        "issued_at": f"{issued_at:.6f}",
    }
    canonical = canonical_json_dumps(payload).encode("utf-8")
    attestation_id = str(doc["attestation_id"])
    subject_zid = str(doc["subject_zid"])
    claim = str(doc["claim"])
    try:
        verifier = Ed25519Verifier(public_pem)
    except Exception:
        return VerificationReport(
            valid=False,
            reason="the embedded public key is not loadable",
            attestation_id=attestation_id,
            subject_zid=subject_zid,
            claim=claim,
            issued_at=issued_at,
            key_fingerprint=None,
        )
    ok = verifier.verify(canonical, signature)
    if not ok:
        return VerificationReport(
            valid=False,
            reason="INVALID signature: this attestation was"
            " tampered or was not issued by the key inside it",
            attestation_id=attestation_id,
            subject_zid=subject_zid,
            claim=claim,
            issued_at=issued_at,
            key_fingerprint=_key_fingerprint(public_pem),
        )
    return VerificationReport(
        valid=True,
        reason="AUTHENTIC: signature verifies against the"
        " embedded public key",
        attestation_id=attestation_id,
        subject_zid=subject_zid,
        claim=claim,
        issued_at=issued_at,
        key_fingerprint=_key_fingerprint(public_pem),
    )
