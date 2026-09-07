"""AES-256-GCM authenticated encryption with key versioning.

Sealed bytes are canonical JSON: format, key_version, nonce
and ciphertext (the 16-byte GCM tag is appended by AESGCM).
AAD binds an envelope to its storage context so captured bytes
cannot be replayed under another record. Keys live in memory
only and come from a KeyProvider; rotation adds versions, it
never rewrites the past.
"""
from __future__ import annotations

import base64
import os
import threading
from collections.abc import Mapping
from dataclasses import dataclass

from cryptography.hazmat.primitives.ciphers.aead import AESGCM

from shared_engines.common.errors import (
    ConfigurationError,
    IntegrityError,
    SerializationError,
)
from shared_engines.common.serialization import (
    canonical_json_dumps,
    canonical_json_loads,
)

KEY_SIZE_BYTES = 32
NONCE_SIZE_BYTES = 12
_ENVELOPE_FORMAT = "zyra.enc.v1"


@dataclass(frozen=True)
class EncryptedEnvelope:
    key_version: int
    nonce: bytes
    ciphertext: bytes


class EnvelopeCrypto:
    def __init__(
        self, keys: Mapping[int, bytes], current_version: int
    ) -> None:
        if not keys:
            raise ConfigurationError("at least one key version required")
        clean: dict[int, bytes] = {}
        for version, key in keys.items():
            if not isinstance(version, int) or version <= 0:
                raise ConfigurationError(
                    "key versions must be positive integers"
                )
            if len(key) != KEY_SIZE_BYTES:
                raise ConfigurationError(
                    f"key v{version} must be {KEY_SIZE_BYTES} bytes"
                )
            clean[version] = bytes(key)
        if current_version not in clean:
            raise ConfigurationError(
                "current_version must be present in keys"
            )
        self._lock = threading.Lock()
        self._keys = clean
        self._current = current_version

    @property
    def current_version(self) -> int:
        with self._lock:
            return self._current

    def encrypt(
        self,
        plaintext: bytes,
        *,
        aad: bytes = b"",
        key_version: int | None = None,
    ) -> EncryptedEnvelope:
        with self._lock:
            version = (
                key_version if key_version is not None else self._current
            )
            key = self._keys.get(version)
        if key is None:
            raise ConfigurationError(
                f"no key configured for version {version}"
            )
        nonce = os.urandom(NONCE_SIZE_BYTES)
        ciphertext = AESGCM(key).encrypt(nonce, plaintext, aad)
        return EncryptedEnvelope(
            key_version=version, nonce=nonce, ciphertext=ciphertext
        )

    def decrypt(
        self, envelope: EncryptedEnvelope, *, aad: bytes = b""
    ) -> bytes:
        with self._lock:
            key = self._keys.get(envelope.key_version)
        if key is None:
            raise IntegrityError(
                "cannot decrypt: key version"
                f" {envelope.key_version} is unknown"
            )
        try:
            return AESGCM(key).decrypt(
                envelope.nonce, envelope.ciphertext, aad
            )
        except Exception as exc:
            raise IntegrityError(
                "decryption failed: wrong key, wrong AAD"
                " or tampered ciphertext"
            ) from exc

    def rotate(self, new_version: int, new_key: bytes) -> None:
        if len(new_key) != KEY_SIZE_BYTES:
            raise ConfigurationError(
                f"new key must be {KEY_SIZE_BYTES} bytes"
            )
        with self._lock:
            if new_version in self._keys:
                raise ConfigurationError(
                    f"key version {new_version} already exists"
                )
            self._keys[new_version] = bytes(new_key)
            self._current = new_version

    def reseal(self, sealed: bytes, *, aad: bytes = b"") -> bytes:
        """Decrypts and re-encrypts to the current key version."""
        return self.seal(self.open(sealed, aad=aad), aad=aad)

    def inspect_key_version(self, sealed: bytes) -> int:
        """Returns the key version without decrypting."""
        return self._parse_sealed(sealed).key_version

    def seal(self, plaintext: bytes, *, aad: bytes = b"") -> bytes:
        envelope = self.encrypt(plaintext, aad=aad)
        token = canonical_json_dumps(
            {
                "format": _ENVELOPE_FORMAT,
                "key_version": envelope.key_version,
                "nonce": base64.b64encode(envelope.nonce).decode("ascii"),
                "ciphertext": base64.b64encode(
                    envelope.ciphertext
                ).decode("ascii"),
            }
        )
        return token.encode("utf-8")

    def open(self, sealed: bytes, *, aad: bytes = b"") -> bytes:
        envelope = self._parse_sealed(sealed)
        return self.decrypt(envelope, aad=aad)

    @staticmethod
    def _parse_sealed(sealed: bytes) -> EncryptedEnvelope:
        try:
            doc = canonical_json_loads(sealed.decode("utf-8"))
        except (UnicodeDecodeError, SerializationError) as exc:
            raise IntegrityError("sealed payload is not decodable") from exc
        if not isinstance(doc, dict) or doc.get("format") != _ENVELOPE_FORMAT:
            raise IntegrityError("unknown envelope format")
        try:
            return EncryptedEnvelope(
                key_version=int(doc["key_version"]),
                nonce=base64.b64decode(str(doc["nonce"]), validate=True),
                ciphertext=base64.b64decode(
                    str(doc["ciphertext"]), validate=True
                ),
            )
        except (KeyError, TypeError, ValueError) as exc:
            raise IntegrityError("malformed sealed envelope") from exc
