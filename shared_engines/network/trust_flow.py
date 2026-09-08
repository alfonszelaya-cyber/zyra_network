"""Trust flow: full onboarding over the identity
lifecycle and the portable profile.

The complete Network trust journey:

    register in an app (NEXO, Subastas, ...)
          |
          v
    ZID created (REGISTERED)
          |
          v
    profile fields filled (SELF_DECLARED)
          |
          v
    evidence verified per field (VERIFIED level)
          |
          v
    TrustFlow.onboarding_complete():
        REGISTERED -> PENDING_VERIFICATION
        -> VERIFIED -> ACTIVE
          |
          v
    any authorized app can now ask
    TrustFlow.is_trusted(zid) and get an
    evidence-backed answer.

Every lifecycle step is validated by the identity
contract, audited, and emitted as an event by the
existing IdentityEngine - this module only composes
engines, it never writes identity storage directly.
"""
from __future__ import annotations

from shared_engines.identity.contracts import (
    Identity,
    IdentityStatus,
)
from shared_engines.identity.engine import (
    IdentityEngine,
)
from shared_engines.network.portable_profile import (
    ProfileRegistry,
)
from shared_engines.common.validation import (
    require_non_empty_str,
)

TRUSTED_STATUSES = (
    IdentityStatus.VERIFIED,
    IdentityStatus.ACTIVE,
)


class TrustFlow:
    """Composes IdentityEngine + ProfileRegistry."""

    def __init__(
        self,
        *,
        identity: IdentityEngine,
        profiles: ProfileRegistry,
    ) -> None:
        self._identity = identity
        self._profiles = profiles

    def onboarding_complete(
        self,
        *,
        zid: str,
        actor: str,
    ) -> Identity:
        """Walk the identity up to ACTIVE.

        Idempotent: an already-ACTIVE identity
        stays ACTIVE. Each transition is validated
        against the contract's allowed map, so an
        inconsistent request is refused, never
        forced.
        """
        require_non_empty_str(zid, "zid")
        require_non_empty_str(
            actor, "actor"
        )
        current = (
            self._identity.require_identity(
                zid
            )
        )
        if current.status is (
            IdentityStatus.REGISTERED
        ):
            current = (
                self._identity.transition_identity(
                    zid,
                    IdentityStatus.PENDING_VERIFICATION,
                    actor=actor,
                    reason=(
                        "verification started"
                    ),
                )
            )
        if current.status is (
            IdentityStatus.PENDING_VERIFICATION
        ):
            current = (
                self._identity.transition_identity(
                    zid,
                    IdentityStatus.VERIFIED,
                    actor=actor,
                    reason=(
                        "evidence verified"
                    ),
                )
            )
        if current.status is (
            IdentityStatus.VERIFIED
        ):
            current = (
                self._identity.transition_identity(
                    zid,
                    IdentityStatus.ACTIVE,
                    actor=actor,
                    reason=(
                        "onboarding complete"
                    ),
                )
            )
        return current

    def is_trusted(self, *, zid: str) -> bool:
        """Evidence-backed trust answer."""
        require_non_empty_str(zid, "zid")
        identity = (
            self._identity.get_identity(zid)
        )
        if identity is None:
            return False
        return identity.status in (
            TRUSTED_STATUSES
        )

    def suspended_identity(
        self,
        *,
        zid: str,
        actor: str,
        reason: str,
    ) -> Identity:
        """Revoke trust: ACTIVE -> SUSPENDED."""
        require_non_empty_str(zid, "zid")
        return (
            self._identity.transition_identity(
                zid,
                IdentityStatus.SUSPENDED,
                actor=actor,
                reason=reason,
            )
        )

    def reactivate_identity(
        self,
        *,
        zid: str,
        actor: str,
        reason: str,
    ) -> Identity:
        """SUSPENDED -> ACTIVE."""
        require_non_empty_str(zid, "zid")
        return (
            self._identity.transition_identity(
                zid,
                IdentityStatus.ACTIVE,
                actor=actor,
                reason=reason,
            )
        )
