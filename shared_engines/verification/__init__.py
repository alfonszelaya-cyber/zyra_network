"""Zyra verification engine.

Verifiable authenticity for the Network: documents, photos,
videos, audio, signed attestations, verifiable credential
history (bank/employer/education records), per-media
provenance chains. Third parties verify offline with the
Network's public key; every state change is audited.
AI-content detection requires real models and arrives as a
dedicated engine; this module does not fake it.
"""
from __future__ import annotations

from shared_engines.verification.attestations import (
    Attestation,
    AttestationIssuer,
)
from shared_engines.verification.credentials import (
    CredentialRecord,
    CredentialRegistry,
    CredentialType,
)
from shared_engines.verification.engine import VerificationEngine
from shared_engines.verification.errors import (
    AttestationNotFoundError,
    CredentialNotFoundError,
    DocumentNotFoundError,
    InvalidSignatureError,
    MediaNotFoundError,
    ProvenanceError,
    SigningKeyError,
    TamperDetectedError,
    VerificationError,
)
from shared_engines.verification.media import (
    MediaKind,
    MediaPage,
    MediaRecord,
    MediaRegistry,
    content_sha256,
)
from shared_engines.verification.provenance import (
    ProvenanceChain,
    ProvenanceEvent,
)
from shared_engines.verification.signatures import (
    Ed25519Signer,
    Ed25519Verifier,
)

__all__ = [
    "Attestation", "AttestationIssuer", "AttestationNotFoundError",
    "CredentialNotFoundError", "CredentialRecord",
    "CredentialRegistry", "CredentialType", "DocumentNotFoundError",
    "Ed25519Signer", "Ed25519Verifier", "InvalidSignatureError",
    "MediaKind", "MediaNotFoundError", "MediaPage", "MediaRecord",
    "MediaRegistry", "ProvenanceChain", "ProvenanceError",
    "ProvenanceEvent", "SigningKeyError", "TamperDetectedError",
    "VerificationEngine", "VerificationError", "content_sha256",
]
