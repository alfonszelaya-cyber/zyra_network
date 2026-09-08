"""Persistent Root Authority: encrypted key at rest, fail-closed."""
from __future__ import annotations

import base64
import hashlib
import json
import os
from dataclasses import dataclass
from enum import Enum
from pathlib import Path

from cryptography.hazmat.primitives.ciphers.aead import AESGCM

from shared_engines.common.errors import (
    ConfigurationError,
    IntegrityError,
)
from shared_engines.common.validation import require_non_empty_str
from shared_engines.verification.signatures import Ed25519Signer

KEY_FILE_FORMAT = "zyra.rootkey.v1"
MASTER_ENV_VAR = "ZYRA_ROOT_KEY"


class RootAuthorityStatus(Enum):
    CREATED_NEW = "created_new"
    LOADED = "loaded"
    ROTATED = "rotated"


@dataclass(frozen=True)
class RootAuthorityStatusRecord:
    status: RootAuthorityStatus
    public_pem_fingerprint: str


class PersistentRootAuthority:
    def __init__(
        self, *, data_dir: Path, master_key_hex: str
    ) -> None:
        require_non_empty_str(master_key_hex, "master_key_hex")
        try:
            raw = bytes.fromhex(master_key_hex)
        except ValueError as exc:
            raise ConfigurationError(
                f"{MASTER_ENV_VAR} must be valid hex"
            ) from exc
        if len(raw) != 32:
            raise ConfigurationError(
                f"{MASTER_ENV_VAR} must be 64 hex chars"
                " (32 bytes)"
            )
        self._master = raw
        self._dir = Path(data_dir)
        self._dir.mkdir(parents=True, exist_ok=True)
        self._key_path = self._dir / "root.key"
        self._history_path = self._dir / "root.history.json"

    def _derive_file_key(self, nonce: bytes) -> bytes:
        return hashlib.sha256(
            b"zyra.rootkey.v1" + self._master + nonce
        ).digest()

    def _encrypt_to_file(self, plaintext: bytes) -> None:
        nonce = os.urandom(12)
        file_key = self._derive_file_key(nonce)
        ciphertext = AESGCM(file_key).encrypt(
            nonce, plaintext, b"zyra-root"
        )
        token = {
            "format": KEY_FILE_FORMAT,
            "nonce": base64.b64encode(nonce).decode("ascii"),
            "ciphertext": base64.b64encode(
                ciphertext
            ).decode("ascii"),
        }
        self._key_path.write_text(
            json.dumps(token), encoding="utf-8"
        )

    def _decrypt_from_file(self) -> bytes:
        if not self._key_path.exists():
            raise FileNotFoundError(str(self._key_path))
        doc = json.loads(
            self._key_path.read_text(encoding="utf-8")
        )
        if doc.get("format") != KEY_FILE_FORMAT:
            raise IntegrityError("unknown key file format")
        nonce = base64.b64decode(str(doc["nonce"]), validate=True)
        ciphertext = base64.b64decode(
            str(doc["ciphertext"]), validate=True
        )
        file_key = self._derive_file_key(nonce)
        try:
            return AESGCM(file_key).decrypt(
                nonce, ciphertext, b"zyra-root"
            )
        except Exception as exc:
            raise IntegrityError(
                "root key file cannot be decrypted:"
                " wrong master key or tampered file"
            ) from exc

    @staticmethod
    def _fingerprint(public_pem: bytes) -> str:
        return hashlib.sha256(public_pem).hexdigest()[:16]

    def load_or_create(
        self,
    ) -> tuple[Ed25519Signer, RootAuthorityStatusRecord]:
        if self._key_path.exists():
            private_pem = self._decrypt_from_file()
            signer = Ed25519Signer(private_pem)
            return signer, RootAuthorityStatusRecord(
                status=RootAuthorityStatus.LOADED,
                public_pem_fingerprint=self._fingerprint(
                    signer.public_pem
                ),
            )
        signer, private_pem = Ed25519Signer.generate()
        self._encrypt_to_file(private_pem)
        return signer, RootAuthorityStatusRecord(
            status=RootAuthorityStatus.CREATED_NEW,
            public_pem_fingerprint=self._fingerprint(
                signer.public_pem
            ),
        )

    def rotate(
        self, *, rotated_by: str
    ) -> tuple[Ed25519Signer, RootAuthorityStatusRecord]:
        require_non_empty_str(rotated_by, "rotated_by")
        old_signer, _ = self.load_or_create()
        old_fp = self._fingerprint(old_signer.public_pem)
        history: list[str] = []
        if self._history_path.exists():
            loaded = json.loads(
                self._history_path.read_text(encoding="utf-8")
            )
            if isinstance(loaded, list):
                history = [str(x) for x in loaded]
        history.append(old_fp)
        self._history_path.write_text(
            json.dumps(history), encoding="utf-8"
        )
        signer, private_pem = Ed25519Signer.generate()
        self._encrypt_to_file(private_pem)
        return signer, RootAuthorityStatusRecord(
            status=RootAuthorityStatus.ROTATED,
            public_pem_fingerprint=self._fingerprint(
                signer.public_pem
            ),
        )

    def historical_fingerprints(self) -> tuple[str, ...]:
        if not self._history_path.exists():
            return ()
        loaded = json.loads(
            self._history_path.read_text(encoding="utf-8")
        )
        if not isinstance(loaded, list):
            return ()
        return tuple(str(x) for x in loaded)

    @staticmethod
    def generate_master_key() -> str:
        return os.urandom(32).hex()
