from __future__ import annotations

import hashlib
import hmac
import secrets
from dataclasses import dataclass
from pathlib import Path
from threading import RLock
from uuid import UUID, uuid4


@dataclass(frozen=True, slots=True)
class BackupArtifact:
    backup_id: UUID
    source: str
    path: str
    digest: str
    size_bytes: int


class BackupEngine:
    """
    Local encrypted-backup primitive.

    The engine uses authenticated encryption semantics based on
    a generated nonce and HMAC-SHA256 over the encrypted payload.
    The key must be supplied by the caller and must never be
    persisted by this component.
    """

    NONCE_SIZE = 32

    def __init__(
        self,
        root: str | Path,
    ) -> None:

        self.root = Path(root)

        self.root.mkdir(
            parents=True,
            exist_ok=True,
        )

        self._lock = RLock()

    @staticmethod
    def _keystream(
        key: bytes,
        nonce: bytes,
        length: int,
    ) -> bytes:

        if not key:
            raise ValueError(
                "Encryption key cannot be empty"
            )

        output = bytearray()
        counter = 0

        while len(output) < length:
            block = hashlib.sha256(
                key
                + nonce
                + counter.to_bytes(
                    8,
                    "big",
                )
            ).digest()

            output.extend(block)
            counter += 1

        return bytes(
            output[:length]
        )

    @classmethod
    def _encrypt(
        cls,
        data: bytes,
        key: bytes,
    ) -> bytes:

        nonce = secrets.token_bytes(
            cls.NONCE_SIZE
        )

        stream = cls._keystream(
            key,
            nonce,
            len(data),
        )

        ciphertext = bytes(
            a ^ b
            for a, b in zip(
                data,
                stream,
            )
        )

        tag = hmac.new(
            key,
            nonce + ciphertext,
            hashlib.sha256,
        ).digest()

        return (
            nonce
            + tag
            + ciphertext
        )

    @classmethod
    def _decrypt(
        cls,
        payload: bytes,
        key: bytes,
    ) -> bytes:

        minimum = (
            cls.NONCE_SIZE
            + hashlib.sha256().digest_size
        )

        if len(payload) < minimum:
            raise ValueError(
                "Invalid encrypted backup payload"
            )

        nonce = payload[
            :cls.NONCE_SIZE
        ]

        tag_start = cls.NONCE_SIZE

        tag_end = (
            tag_start
            + hashlib.sha256().digest_size
        )

        tag = payload[
            tag_start:tag_end
        ]

        ciphertext = payload[
            tag_end:
        ]

        expected = hmac.new(
            key,
            nonce + ciphertext,
            hashlib.sha256,
        ).digest()

        if not hmac.compare_digest(
            tag,
            expected,
        ):
            raise ValueError(
                "Backup authentication failed"
            )

        stream = cls._keystream(
            key,
            nonce,
            len(ciphertext),
        )

        return bytes(
            a ^ b
            for a, b in zip(
                ciphertext,
                stream,
            )
        )

    def create_backup(
        self,
        source: str,
        data: bytes,
        key: bytes,
    ) -> BackupArtifact:

        encrypted = self._encrypt(
            bytes(data),
            bytes(key),
        )

        backup_id = uuid4()

        filename = (
            f"{backup_id.hex}.backup"
        )

        path = self.root / filename

        with self._lock:
            path.write_bytes(
                encrypted
            )

        digest = hashlib.sha256(
            encrypted
        ).hexdigest()

        return BackupArtifact(
            backup_id=backup_id,
            source=source,
            path=str(path),
            digest=digest,
            size_bytes=len(encrypted),
        )

    def restore(
        self,
        artifact: BackupArtifact,
        key: bytes,
    ) -> bytes:

        path = Path(
            artifact.path
        )

        with self._lock:
            payload = path.read_bytes()

        digest = hashlib.sha256(
            payload
        ).hexdigest()

        if not hmac.compare_digest(
            digest,
            artifact.digest,
        ):
            raise ValueError(
                "Backup digest verification failed"
            )

        return self._decrypt(
            payload,
            bytes(key),
        )


__all__ = [
    "BackupArtifact",
    "BackupEngine",
]
