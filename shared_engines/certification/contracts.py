"""Certification contracts."""
from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class IssuerRecord:
    issuer_id: str
    display_name: str
    scopes: tuple[str, ...]
    registered_at: float
    active: bool


@dataclass(frozen=True)
class CertificateRecord:
    certificate_id: str
    subject_zid: str
    issuer_id: str
    scope: str
    title: str
    detail: str
    evidence: tuple[str, ...]
    credential_id: str
    signature: bytes
    public_pem: bytes
    issued_at: float
    valid_until: float | None
    revoked: bool


@dataclass(frozen=True)
class CertificationVerdict:
    """Evidence-backed certification answer."""

    certificate_id: str
    signature_valid: bool
    within_validity: bool
    issuer_authorized: bool
    not_revoked: bool
    valid: bool
    credential_id: str
    evidence: dict[str, object]
