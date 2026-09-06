from __future__ import annotations

import hashlib
import hmac
from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class ProtocolIdentity:
    subject_id: str
    issuer_id: str
    fingerprint: str

    @classmethod
    def create(
        cls,
        subject_id: str,
        issuer_id: str,
        identity_material: bytes,
    ) -> "ProtocolIdentity":
        if not subject_id.strip():
            raise ValueError("Subject ID cannot be empty")
        if not issuer_id.strip():
            raise ValueError("Issuer ID cannot be empty")
        if not identity_material:
            raise ValueError("Identity material cannot be empty")

        fingerprint = hashlib.sha256(
            identity_material
        ).hexdigest()

        return cls(
            subject_id=subject_id.strip(),
            issuer_id=issuer_id.strip(),
            fingerprint=fingerprint,
        )


class IdentityRegistry:
    def __init__(self) -> None:
        self._identities: dict[str, ProtocolIdentity] = {}

    def register(self, identity: ProtocolIdentity) -> None:
        if identity.subject_id in self._identities:
            raise ValueError(
                f"Identity already registered: "
                f"{identity.subject_id}"
            )

        self._identities[identity.subject_id] = identity

    def resolve(self, subject_id: str) -> ProtocolIdentity:
        return self._identities[subject_id.strip()]

    def verify(
        self,
        identity: ProtocolIdentity,
        identity_material: bytes,
    ) -> bool:
        expected = hashlib.sha256(
            identity_material
        ).hexdigest()

        return (
            hmac.compare_digest(
                expected,
                identity.fingerprint,
            )
            and identity.subject_id
            in self._identities
            and self._identities[identity.subject_id] == identity
        )


__all__ = ["ProtocolIdentity", "IdentityRegistry"]
