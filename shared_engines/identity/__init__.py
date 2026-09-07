"""Zyra identity engine: unique ids, permanent registry, history."""
from __future__ import annotations

from shared_engines.identity.contracts import (
    IDENTITY_CONTRACT_VERSION,
    Identity,
    IdentityKind,
    IdentityStatus,
    VALID_TRANSITIONS,
)
from shared_engines.identity.engine import IdentityEngine
from shared_engines.identity.errors import (
    IdentityAlreadyExistsError,
    IdentityError,
    IdentityNotFoundError,
    InvalidTransitionError,
)
from shared_engines.identity.registry import IdentityRegistry

__all__ = [
    "IDENTITY_CONTRACT_VERSION", "Identity", "IdentityEngine",
    "IdentityAlreadyExistsError", "IdentityError",
    "IdentityKind", "IdentityNotFoundError", "IdentityRegistry",
    "IdentityStatus", "InvalidTransitionError", "VALID_TRANSITIONS",
]
