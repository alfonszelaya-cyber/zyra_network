from __future__ import annotations

import hashlib
import hmac
from dataclasses import dataclass


DEFAULT_DIGEST = "sha256"


@dataclass(frozen=True, slots=True)
class VerificationResult:
    valid: bool
    algorithm: str
    fingerprint: str


class ProtocolVerifier:

    def __init__(
        self,
        algorithm: str = DEFAULT_DIGEST,
    ) -> None:

        normalized = (
            algorithm.strip().lower()
        )

        if normalized not in (
            hashlib.algorithms_available
        ):
            raise ValueError(
                f"Unsupported digest algorithm: "
                f"{algorithm}"
            )

        self.algorithm = normalized

    def fingerprint(
        self,
        payload: bytes,
    ) -> str:

        if not isinstance(
            payload,
            bytes,
        ):
            raise TypeError(
                "Verification payload "
                "must be bytes"
            )

        return hashlib.new(
            self.algorithm,
            payload,
        ).hexdigest()

    def verify_fingerprint(
        self,
        payload: bytes,
        expected: str,
    ) -> bool:

        actual = self.fingerprint(
            payload
        )

        return hmac.compare_digest(
            actual,
            expected.strip().lower(),
        )

    def sign_hmac(
        self,
        payload: bytes,
        secret: bytes,
    ) -> bytes:

        if not isinstance(
            payload,
            bytes,
        ):
            raise TypeError(
                "payload must be bytes"
            )

        if not isinstance(
            secret,
            bytes,
        ):
            raise TypeError(
                "secret must be bytes"
            )

        if not secret:
            raise ValueError(
                "secret cannot be empty"
            )

        return hmac.new(
            secret,
            payload,
            self.algorithm,
        ).digest()

    def verify_hmac(
        self,
        payload: bytes,
        secret: bytes,
        expected: bytes,
    ) -> bool:

        if not isinstance(
            payload,
            bytes,
        ):
            raise TypeError(
                "payload must be bytes"
            )

        if not isinstance(
            secret,
            bytes,
        ):
            raise TypeError(
                "secret must be bytes"
            )

        if not isinstance(
            expected,
            bytes,
        ):
            raise TypeError(
                "expected must be bytes"
            )

        if not secret:
            raise ValueError(
                "secret cannot be empty"
            )

        actual = self.sign_hmac(
            payload,
            secret,
        )

        return hmac.compare_digest(
            actual,
            expected,
        )

    def verify(
        self,
        payload: bytes,
        expected_fingerprint: str,
    ) -> VerificationResult:

        fingerprint = self.fingerprint(
            payload
        )

        return VerificationResult(
            valid=hmac.compare_digest(
                fingerprint,
                expected_fingerprint
                .strip()
                .lower(),
            ),
            algorithm=self.algorithm,
            fingerprint=fingerprint,
        )


__all__ = [
    "DEFAULT_DIGEST",
    "VerificationResult",
    "ProtocolVerifier",
]
