"""Trust flow proofs: lifecycle walk to ACTIVE,
evidence-backed is_trusted, suspension and
reactivation."""
from __future__ import annotations

from pathlib import Path

from shared_engines.audit.chain import AuditTrail
from shared_engines.common.clocks import (
    FrozenClock,
)
from shared_engines.events.contracts import (
    EventCatalog,
)
from shared_engines.events.outbox import Outbox
from shared_engines.identity.contracts import (
    IdentityKind,
    IdentityStatus,
)
from shared_engines.identity.engine import (
    IdentityEngine,
)
from shared_engines.network.portable_profile import (
    ProfileRegistry,
)
from shared_engines.network.trust_flow import (
    TrustFlow,
)
from shared_engines.storage.database import (
    SQLiteAdapter,
)


class _Net:
    def __init__(
        self, tmp_path: Path
    ) -> None:
        self.db = SQLiteAdapter(
            tmp_path / "net.db"
        )
        self.clock = FrozenClock()
        self.audit = AuditTrail(
            self.db, self.clock
        )
        self.outbox = Outbox(
            self.db, self.clock
        )
        self.outbox.ensure_schema()
        self.catalog = EventCatalog()
        for et in (
            "identity.registered",
            "identity.status_changed",
            "network.profile.updated",
            "network.profile.accessed",
        ):
            self.catalog.register(et)
        self.identity = IdentityEngine(
            db=self.db,
            clock=self.clock,
            audit=self.audit,
            outbox=self.outbox,
            catalog=self.catalog,
        )
        self.profiles = ProfileRegistry(
            self.db,
            self.clock,
            audit=self.audit,
            outbox=self.outbox,
        )
        self.flow = TrustFlow(
            identity=self.identity,
            profiles=self.profiles,
        )

    def close(self) -> None:
        self.db.close()


def test_full_lifecycle_to_active(
    tmp_path: Path,
) -> None:
    net = _Net(tmp_path)
    try:
        net.profiles.register_app(
            app_id="nexo",
            display_name="NEXO",
            scopes=("display_name",),
        )
        user = (
            net.identity.register_identity(
                kind=IdentityKind.PERSON,
                display_name="carla",
                actor="nexo",
            )
        )
        assert user.status is (
            IdentityStatus.REGISTERED
        )
        assert (
            net.flow.is_trusted(zid=user.zid)
            is False
        )
        net.profiles.set_field(
            zid=user.zid,
            field="display_name",
            value="Carla Ruiz",
            verified=True,
        )
        final = net.flow.onboarding_complete(
            zid=user.zid,
            actor="verifier",
        )
        assert final.status is (
            IdentityStatus.ACTIVE
        )
        assert (
            net.flow.is_trusted(zid=user.zid)
            is True
        )
        # Idempotent: stays ACTIVE
        again = net.flow.onboarding_complete(
            zid=user.zid,
            actor="verifier",
        )
        assert again.status is (
            IdentityStatus.ACTIVE
        )
        assert net.audit.verify() >= 4
    finally:
        net.close()


def test_is_trusted_unknown_zid(
    tmp_path: Path,
) -> None:
    net = _Net(tmp_path)
    try:
        assert (
            net.flow.is_trusted(
                zid="ZID-nope"
            )
            is False
        )
    finally:
        net.close()


def test_suspend_and_reactivate(
    tmp_path: Path,
) -> None:
    net = _Net(tmp_path)
    try:
        user = (
            net.identity.register_identity(
                kind=IdentityKind.PERSON,
                display_name="d",
                actor="t",
            )
        )
        net.flow.onboarding_complete(
            zid=user.zid,
            actor="verifier",
        )
        suspended = (
            net.flow.suspended_identity(
                zid=user.zid,
                actor="ops",
                reason="fraud alert",
            )
        )
        assert suspended.status is (
            IdentityStatus.SUSPENDED
        )
        assert (
            net.flow.is_trusted(zid=user.zid)
            is False
        )
        back = net.flow.reactivate_identity(
            zid=user.zid,
            actor="ops",
            reason="alert cleared",
        )
        assert back.status is (
            IdentityStatus.ACTIVE
        )
        assert (
            net.flow.is_trusted(zid=user.zid)
            is True
        )
    finally:
        net.close()
