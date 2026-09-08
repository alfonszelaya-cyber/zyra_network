"""Portable identity proofs: register in one app,
recognized in another; scoped visibility; audited
access; verified levels."""
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
)
from shared_engines.identity.engine import (
    IdentityEngine,
)
from shared_engines.network.portable_profile import (
    LEVEL_SELF,
    LEVEL_VERIFIED,
    ProfileRegistry,
)
from shared_engines.storage.database import (
    SQLiteAdapter,
)
from shared_engines.telemetry.collector import (
    TelemetryCollector,
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
        self.telemetry = TelemetryCollector(
            self.db, self.clock
        )

    def close(self) -> None:
        self.db.close()


def test_register_once_recognized_everywhere(
    tmp_path: Path,
) -> None:
    net = _Net(tmp_path)
    try:
        net.profiles.register_app(
            app_id="nexo",
            display_name="NEXO",
            scopes=(
                "display_name",
                "contact",
            ),
        )
        net.profiles.register_app(
            app_id="subastas",
            display_name="Subastas",
            scopes=("display_name",),
        )
        user = (
            net.identity.register_identity(
                kind=IdentityKind.PERSON,
                display_name="maria",
                actor="nexo",
            )
        )
        net.profiles.set_field(
            zid=user.zid,
            field="display_name",
            value="Maria Lopez",
        )
        net.profiles.set_field(
            zid=user.zid,
            field="contact",
            value="maria@zyra.sv",
        )
        view_nexo = (
            net.profiles.view_for_app(
                app_id="nexo",
                zid=user.zid,
            )
        )
        assert (
            view_nexo.fields[
                "display_name"
            ]
            == "Maria Lopez"
        )
        assert (
            view_nexo.fields["contact"]
            == "maria@zyra.sv"
        )
        view_sub = (
            net.profiles.view_for_app(
                app_id="subastas",
                zid=user.zid,
            )
        )
        assert (
            view_sub.fields[
                "display_name"
            ]
            == "Maria Lopez"
        )
        assert "contact" not in (
            view_sub.fields
        )
    finally:
        net.close()


def test_unregistered_app_denied(
    tmp_path: Path,
) -> None:
    net = _Net(tmp_path)
    try:
        user = (
            net.identity.register_identity(
                kind=IdentityKind.PERSON,
                display_name="luis",
                actor="t",
            )
        )
        try:
            net.profiles.view_for_app(
                app_id="malware",
                zid=user.zid,
            )
            raise AssertionError(
                "expected"
                " PermissionError"
            )
        except PermissionError:
            pass
    finally:
        net.close()


def test_verified_level_and_telemetry(
    tmp_path: Path,
) -> None:
    net = _Net(tmp_path)
    try:
        net.profiles.register_app(
            app_id="gov",
            display_name="Gov",
            scopes=("national_id",),
        )
        user = (
            net.identity.register_identity(
                kind=IdentityKind.PERSON,
                display_name="ana",
                actor="t",
            )
        )
        net.profiles.set_field(
            zid=user.zid,
            field="national_id",
            value="XXXXXXXXXX",
            verified=True,
        )
        view = net.profiles.view_for_app(
            app_id="gov", zid=user.zid
        )
        assert (
            view.levels["national_id"]
            == LEVEL_VERIFIED
        )
        assert (
            view.levels["national_id"]
            != LEVEL_SELF
        )
        net.telemetry.ingest_outbox(
            net.outbox
        )
        accessed = (
            net.telemetry.query_events(
                event_type=(
                    "network.profile"
                    ".accessed"
                )
            )
        )
        assert len(accessed) >= 1
    finally:
        net.close()


def test_audit_trail_records_access(
    tmp_path: Path,
) -> None:
    net = _Net(tmp_path)
    try:
        net.profiles.register_app(
            app_id="a1",
            display_name="A1",
            scopes=("display_name",),
        )
        user = (
            net.identity.register_identity(
                kind=IdentityKind.PERSON,
                display_name="b",
                actor="t",
            )
        )
        net.profiles.set_field(
            zid=user.zid,
            field="display_name",
            value="B",
        )
        net.profiles.view_for_app(
            app_id="a1", zid=user.zid
        )
        count = net.audit.verify()
        assert count >= 1
    finally:
        net.close()
