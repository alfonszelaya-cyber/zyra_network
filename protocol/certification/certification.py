from __future__ import annotations

import hashlib
from dataclasses import dataclass
from datetime import datetime, timezone


@dataclass(frozen=True, slots=True)
class Certificate:
    subject: str
    issuer: str
    fingerprint: str
    issued_at: datetime

    @classmethod
    def issue(
        cls,
        subject: str,
        issuer: str,
        public_material: bytes,
    ) -> "Certificate":
        if not subject.strip():
            raise ValueError("Certificate subject cannot be empty")
        if not issuer.strip():
            raise ValueError("Certificate issuer cannot be empty")
        if not public_material:
            raise ValueError("Public material cannot be empty")

        fingerprint = hashlib.sha256(public_material).hexdigest()

        return cls(
            subject=subject.strip(),
            issuer=issuer.strip(),
            fingerprint=fingerprint,
            issued_at=datetime.now(timezone.utc),
        )


class CertificateAuthority:
    """Local protocol-level certificate authority registry."""

    def __init__(self, authority_id: str) -> None:
        if not authority_id.strip():
            raise ValueError("Authority ID cannot be empty")

        self.authority_id = authority_id.strip()
        self._certificates: dict[str, Certificate] = {}

    def issue(
        self,
        subject: str,
        public_material: bytes,
    ) -> Certificate:
        certificate = Certificate.issue(
            subject=subject,
            issuer=self.authority_id,
            public_material=public_material,
        )

        if subject.strip() in self._certificates:
            raise ValueError(
                f"Certificate already exists: {subject.strip()}"
            )

        self._certificates[subject.strip()] = certificate
        return certificate

    def verify(self, certificate: Certificate) -> bool:
        return (
            certificate.issuer == self.authority_id
            and certificate.subject in self._certificates
            and self._certificates[certificate.subject]
            == certificate
        )

    def get(self, subject: str) -> Certificate:
        return self._certificates[subject.strip()]


__all__ = ["Certificate", "CertificateAuthority"]
