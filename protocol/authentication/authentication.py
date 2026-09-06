from __future__ import annotations

import base64
import hashlib
import hmac
import secrets
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone


@dataclass(frozen=True, slots=True)
class AuthenticationChallenge:
    challenge: str
    issued_at: datetime
    expires_at: datetime

    @classmethod
    def create(cls, lifetime_seconds: int = 300) -> "AuthenticationChallenge":
        if lifetime_seconds <= 0:
            raise ValueError("Challenge lifetime must be positive")

        issued = datetime.now(timezone.utc)

        return cls(
            challenge=secrets.token_urlsafe(32),
            issued_at=issued,
            expires_at=issued + timedelta(seconds=lifetime_seconds),
        )

    def is_expired(self, now: datetime | None = None) -> bool:
        current = now or datetime.now(timezone.utc)
        return current >= self.expires_at


class AuthenticationVerifier:
    """Challenge-response verifier using HMAC-SHA256."""

    def __init__(self, secret: bytes) -> None:
        if not secret:
            raise ValueError("Authentication secret cannot be empty")

        self._secret = bytes(secret)

    def create_response(self, challenge: str) -> str:
        if not challenge:
            raise ValueError("Challenge cannot be empty")

        digest = hmac.new(
            self._secret,
            challenge.encode("utf-8"),
            hashlib.sha256,
        ).digest()

        return base64.urlsafe_b64encode(digest).decode("ascii")

    def verify(self, challenge: str, response: str) -> bool:
        expected = self.create_response(challenge)

        return hmac.compare_digest(expected, response)


__all__ = [
    "AuthenticationChallenge",
    "AuthenticationVerifier",
]
