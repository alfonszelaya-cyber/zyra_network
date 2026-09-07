"""Typed verification errors."""
from __future__ import annotations

from shared_engines.common.errors import (
    ConfigurationError,
    EngineError,
    IntegrityError,
    NotFoundError,
)


class VerificationError(EngineError):
    """Base for verification engine failures."""


class DocumentNotFoundError(VerificationError, NotFoundError):
    """No document exists for the given id."""


class MediaNotFoundError(VerificationError, NotFoundError):
    """No media item exists for the given id."""


class TamperDetectedError(VerificationError, IntegrityError):
    """Content does not match the registered fingerprint."""


class InvalidSignatureError(VerificationError, IntegrityError):
    """A signature does not verify against the claimed key."""


class SigningKeyError(VerificationError, ConfigurationError):
    """A signing/verification key could not be loaded."""


class AttestationNotFoundError(VerificationError, NotFoundError):
    """No attestation exists for the given id."""


class CredentialNotFoundError(VerificationError, NotFoundError):
    """No credential exists for the given id."""


class ProvenanceError(VerificationError, IntegrityError):
    """The provenance chain is broken or inconsistent."""
