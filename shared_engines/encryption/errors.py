"""Typed encryption-engine errors.

Cryptographic failures themselves surface as the
existing typed errors of security.crypto
(IntegrityError, ConfigurationError); this module
adds engine-level lifecycle errors only.
"""
from __future__ import annotations

from shared_engines.common.errors import (
    EngineError,
)


class EncryptionError(EngineError):
    """Base encryption-engine error."""


class KeyStateError(EncryptionError):
    """Illegal key lifecycle operation."""
