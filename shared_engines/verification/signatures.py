"""Ed25519 digital signatures.

Real asymmetric cryptography: the Network signs with its
private key; anyone with the public key verifies. Signatures
are compact (64 bytes) and third-party verifiable without
any database access.
"""
from __future__ import annotations

from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric.ed25519 import (
    Ed25519PrivateKey,
    Ed25519PublicKey,
)

from shared_engines.verification.errors import SigningKeyError


class Ed25519Signer:
    """Holds the private signing key; signs canonical bytes."""

    def __init__(self, private_pem: bytes) -> None:
        try:
            key = serialization.load_pem_private_key(
                private_pem, password=None
            )
        except Exception as exc:
            raise SigningKeyError(
                "private key PEM is not loadable"
            ) from exc
        if not isinstance(key, Ed25519PrivateKey):
            raise SigningKeyError("signing key must be Ed25519")
        self._key = key

    @classmethod
    def generate(cls) -> tuple[Ed25519Signer, bytes]:
        """Returns (signer, private_pem). Store the PEM safely."""
        private = Ed25519PrivateKey.generate()
        private_pem = private.private_bytes(
            encoding=serialization.Encoding.PEM,
            format=serialization.PrivateFormat.PKCS8,
            encryption_algorithm=serialization.NoEncryption(),
        )
        return cls(private_pem), private_pem

    @property
    def public_pem(self) -> bytes:
        return self._key.public_key().public_bytes(
            encoding=serialization.Encoding.PEM,
            format=serialization.PublicFormat.SubjectPublicKeyInfo,
        )

    def sign(self, data: bytes) -> bytes:
        return self._key.sign(data)


class Ed25519Verifier:
    """Verifies signatures against a public key.

    This is the object a third party uses to check a Zyra
    attestation offline.
    """

    def __init__(self, public_pem: bytes) -> None:
        try:
            key = serialization.load_pem_public_key(public_pem)
        except Exception as exc:
            raise SigningKeyError(
                "public key PEM is not loadable"
            ) from exc
        if not isinstance(key, Ed25519PublicKey):
            raise SigningKeyError(
                "verification key must be Ed25519"
            )
        self._key = key

    def verify(self, data: bytes, signature: bytes) -> bool:
        try:
            self._key.verify(signature, data)
        except Exception:
            return False
        return True
