"""Key providers feeding ``EnvelopeCrypto`` from managed sources.

This is the KMS/HSM/secret-manager adapter point: implement
``KeyProvider`` against the real service at the composition
root. Secrets are read at runtime and never logged or
persisted here.
"""
from __future__ import annotations

import os
from collections.abc import Mapping
from typing import Protocol

from shared_engines.common.errors import ConfigurationError
from shared_engines.security.crypto import EnvelopeCrypto


class KeyProvider(Protocol):
    def load_keys(self) -> Mapping[int, bytes]:
        ...

    @property
    def current_version(self) -> int:
        ...


class StaticKeyProvider:
    """Explicit mapping; useful for tests and in-memory use."""

    def __init__(
        self, keys: Mapping[int, bytes], current_version: int
    ) -> None:
        self._keys = dict(keys)
        self._current = current_version

    def load_keys(self) -> Mapping[int, bytes]:
        return dict(self._keys)

    @property
    def current_version(self) -> int:
        return self._current


class EnvironmentKeyProvider:
    """Reads 32-byte hex keys from ``<prefix>_V<version>`` env
    variables; ``<prefix>_CURRENT`` names the active version."""

    def __init__(
        self,
        prefix: str = "ZYRA_MASTER_KEY",
        env: Mapping[str, str] | None = None,
    ) -> None:
        self._prefix = prefix
        self._env = dict(os.environ if env is None else env)
        self._current: int | None = None

    def load_keys(self) -> Mapping[int, bytes]:
        keys: dict[int, bytes] = {}
        prefix = f"{self._prefix}_V"
        for name, value in self._env.items():
            if not name.startswith(prefix):
                continue
            suffix = name[len(prefix):]
            if not suffix.isdigit():
                continue
            try:
                keys[int(suffix)] = bytes.fromhex(value)
            except ValueError as exc:
                raise ConfigurationError(
                    f"key env var {name} is not valid hex"
                ) from exc
        if not keys:
            raise ConfigurationError(
                f"no keys configured via {self._prefix}_V<version>"
            )
        current_raw = self._env.get(f"{self._prefix}_CURRENT")
        if (
            current_raw is None
            or not current_raw.isdigit()
            or int(current_raw) not in keys
        ):
            raise ConfigurationError(
                f"{self._prefix}_CURRENT must name a configured version"
            )
        self._current = int(current_raw)
        return keys

    @property
    def current_version(self) -> int:
        if self._current is None:
            self.load_keys()
        if self._current is None:
            raise ConfigurationError("no current key version available")
        return self._current


def crypto_from_provider(provider: KeyProvider) -> EnvelopeCrypto:
    keys = provider.load_keys()
    return EnvelopeCrypto(keys, provider.current_version)
