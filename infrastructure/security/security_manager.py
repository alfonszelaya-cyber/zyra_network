"""
Provider-neutral infrastructure authorization boundary.

Identity issuance and external authentication remain in their
dedicated protocol/security layers.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from time import time
from typing import FrozenSet, Mapping


class AccessDecision(str, Enum):
    ALLOW = "allow"
    DENY = "deny"


@dataclass(frozen=True, slots=True)
class SecurityContext:
    principal: str
    roles: FrozenSet[str] = frozenset()
    claims: Mapping[str, str] = field(
        default_factory=dict
    )
    issued_at: float = field(
        default_factory=time
    )

    def __post_init__(self) -> None:
        if not self.principal.strip():
            raise ValueError(
                "principal is required"
            )


class SecurityManager:
    """Minimal deterministic role authorization boundary."""

    def __init__(self) -> None:
        self._policies: dict[
            str,
            frozenset[str],
        ] = {}

    def require_role(
        self,
        resource: str,
        role: str,
    ) -> None:
        if not resource.strip():
            raise ValueError(
                "resource is required"
            )

        if not role.strip():
            raise ValueError(
                "role is required"
            )

        current = set(
            self._policies.get(
                resource,
                frozenset(),
            )
        )

        current.add(role)

        self._policies[
            resource
        ] = frozenset(current)

    def authorize(
        self,
        context: SecurityContext,
        resource: str,
    ) -> AccessDecision:
        if not isinstance(
            context,
            SecurityContext,
        ):
            raise TypeError(
                "context must be SecurityContext"
            )

        required = self._policies.get(
            resource,
            frozenset(),
        )

        if not required:
            return AccessDecision.ALLOW

        if required.intersection(
            context.roles
        ):
            return AccessDecision.ALLOW

        return AccessDecision.DENY


__all__ = [
    "AccessDecision",
    "SecurityContext",
    "SecurityManager",
]
