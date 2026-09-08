"""Encryption engine: high-level facade over the
existing EnvelopeCrypto (security/crypto.py).

Adds what crypto.py intentionally lacks: durable
key persistence. The sealed format, AES-GCM
primitives, AAD binding and zyra.enc.v1 envelope
are REUSED, never duplicated. Rotation here is
durable: after a restart, every historical
version is still available and old envelopes
stay openable.
"""
from __future__ import annotations

from shared_engines.common.clocks import Clock
from shared_engines.encryption.contracts import (
    KeyRecord,
)
from shared_engines.encryption.keyring import (
    DurableKeyring,
)
from shared_engines.security.crypto import (
    EnvelopeCrypto,
)
from shared_engines.storage.database import (
    Database,
)


class EncryptionEngine:
    """Durable sealed storage via EnvelopeCrypto."""

    def __init__(
        self,
        db: Database,
        clock: Clock,
        *,
        namespace: str = "default",
    ) -> None:
        self._keyring = DurableKeyring(
            db,
            clock,
            namespace=namespace,
        )
        self._crypto = self._reload()

    def _reload(self) -> EnvelopeCrypto:
        keys = (
            self._keyring.load_keys()
        )
        current = (
            self._keyring.current_version()
        )
        return EnvelopeCrypto(
            keys, current
        )

    def seal(
        self,
        data: bytes,
        *,
        aad: bytes = b"",
    ) -> bytes:
        return self._crypto.seal(
            data, aad=aad
        )

    def open(
        self,
        sealed: bytes,
        *,
        aad: bytes = b"",
    ) -> bytes:
        return self._crypto.open(
            sealed, aad=aad
        )

    def reseal(
        self,
        sealed: bytes,
        *,
        aad: bytes = b"",
    ) -> bytes:
        return self._crypto.reseal(
            sealed, aad=aad
        )

    def inspect_key_version(
        self, sealed: bytes
    ) -> int:
        return (
            self._crypto.inspect_key_version(
                sealed
            )
        )

    def rotate(self) -> int:
        """Durable rotation; survives
        restarts."""
        version = (
            self._keyring.rotate()
        )
        self._crypto = self._reload()
        return version

    def key_history(
        self,
    ) -> tuple[KeyRecord, ...]:
        return (
            self._keyring.history()
        )
