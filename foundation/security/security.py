from __future__ import annotations

import hashlib
import hmac
import secrets
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone


class SecurityError(RuntimeError):
    """Base foundation security failure."""


class SecretValidationError(SecurityError):
    """Invalid secret or security parameter."""


@dataclass(frozen=True, slots=True)
class SecretDigest:
    algorithm: str
    digest: str
    created_at: datetime

    def to_dict(self) -> dict[str, str]:
        return {
            "algorithm": self.algorithm,
            "digest": self.digest,
            "created_at":
                self.created_at.isoformat(),
        }


class SecurityPrimitives:
    """
    Cryptographic foundation primitives.

    Uses Python's standard-library cryptography primitives for
    secure random values, SHA-256 integrity digests and constant
    time comparisons. Higher-level authentication, credentials
    and certificates belong to protocol/shared security layers.
    """

    HASH_ALGORITHM = "sha256"

    @staticmethod
    def random_token(
        length: int = 32,
    ) -> str:
        if length < 16:
            raise SecretValidationError(
                "Token length must be >= 16"
            )

        return secrets.token_urlsafe(length)

    @classmethod
    def digest(
        cls,
        value: bytes | str,
    ) -> SecretDigest:
        data = cls._bytes(value)

        digest = hashlib.sha256(
            data
        ).hexdigest()

        return SecretDigest(
            algorithm=cls.HASH_ALGORITHM,
            digest=digest,
            created_at=datetime.now(
                timezone.utc
            ),
        )

    @staticmethod
    def verify_digest(
        value: bytes | str,
        expected_digest: str,
    ) -> bool:
        if not isinstance(
            expected_digest,
            str,
        ):
            return False

        data = (
            value.encode("utf-8")
            if isinstance(value, str)
            else value
        )

        actual = hashlib.sha256(
            data
        ).hexdigest()

        return hmac.compare_digest(
            actual,
            expected_digest,
        )

    @staticmethod
    def constant_time_equal(
        left: str | bytes,
        right: str | bytes,
    ) -> bool:
        left_bytes = SecurityPrimitives._bytes(
            left
        )

        right_bytes = SecurityPrimitives._bytes(
            right
        )

        return hmac.compare_digest(
            left_bytes,
            right_bytes,
        )

    @staticmethod
    def expiration(
        lifetime_seconds: int,
    ) -> datetime:
        if lifetime_seconds <= 0:
            raise SecretValidationError(
                "Lifetime must be positive"
            )

        return (
            datetime.now(timezone.utc)
            + timedelta(
                seconds=lifetime_seconds
            )
        )

    @staticmethod
    def is_expired(
        expires_at: datetime,
    ) -> bool:
        if expires_at.tzinfo is None:
            raise SecretValidationError(
                "Expiration must be timezone-aware"
            )

        return (
            datetime.now(timezone.utc)
            >= expires_at
        )

    @staticmethod
    def _bytes(
        value: bytes | str,
    ) -> bytes:
        if isinstance(value, bytes):
            return value

        if isinstance(value, str):
            return value.encode("utf-8")

        raise TypeError(
            "Value must be bytes or string"
        )
