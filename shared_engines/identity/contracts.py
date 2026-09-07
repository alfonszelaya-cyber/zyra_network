"""Versioned identity contracts (contract v1).

A ZID is opaque, unique and immutable. Lifecycle: REGISTERED
-> PENDING_VERIFICATION -> VERIFIED -> ACTIVE; ACTIVE ->
SUSPENDED -> ACTIVE; terminal REVOKED from any non-revoked
state. Every transition is validated before it is applied.
"""
from __future__ import annotations

from dataclasses import dataclass
from enum import Enum

from shared_engines.common.errors import ValidationError
from shared_engines.common.validation import (
    require_int_range,
    require_non_empty_str,
)

IDENTITY_CONTRACT_VERSION = 1


class IdentityKind(Enum):
    PERSON = "person"
    ORGANIZATION = "organization"
    DEVICE = "device"
    INSTITUTION = "institution"


class IdentityStatus(Enum):
    REGISTERED = "REGISTERED"
    PENDING_VERIFICATION = "PENDING_VERIFICATION"
    VERIFIED = "VERIFIED"
    ACTIVE = "ACTIVE"
    SUSPENDED = "SUSPENDED"
    REVOKED = "REVOKED"


VALID_TRANSITIONS: dict[IdentityStatus, frozenset[IdentityStatus]] = {
    IdentityStatus.REGISTERED: frozenset(
        {
            IdentityStatus.PENDING_VERIFICATION,
            IdentityStatus.ACTIVE,
            IdentityStatus.REVOKED,
        }
    ),
    IdentityStatus.PENDING_VERIFICATION: frozenset(
        {IdentityStatus.VERIFIED, IdentityStatus.REVOKED}
    ),
    IdentityStatus.VERIFIED: frozenset(
        {IdentityStatus.ACTIVE, IdentityStatus.REVOKED}
    ),
    IdentityStatus.ACTIVE: frozenset(
        {IdentityStatus.SUSPENDED, IdentityStatus.REVOKED}
    ),
    IdentityStatus.SUSPENDED: frozenset(
        {IdentityStatus.ACTIVE, IdentityStatus.REVOKED}
    ),
    IdentityStatus.REVOKED: frozenset(),
}


@dataclass(frozen=True)
class Identity:
    zid: str
    kind: IdentityKind
    status: IdentityStatus
    display_name: str
    created_at: float
    updated_at: float
    contract_version: int = IDENTITY_CONTRACT_VERSION

    def __post_init__(self) -> None:
        require_non_empty_str(self.zid, "zid")
        require_non_empty_str(self.display_name, "display_name")
        require_int_range(
            self.contract_version, "contract_version", 1, 100
        )
        if not isinstance(self.kind, IdentityKind):
            raise ValidationError("kind must be IdentityKind")
        if not isinstance(self.status, IdentityStatus):
            raise ValidationError("status must be IdentityStatus")
