"""Lifelong history proofs: a newborn registered in
a health app starts a tamper-evident civic timeline
that other authorized apps extend over time."""
from __future__ import annotations

from pathlib import Path

import pytest

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
from shared_engines.network.life_history import (
    LifeHistory,
)
from shared_engines.network.portable_profile import (
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
            "network.history.appended",
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
        self.history = LifeHistory(
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


def test_newborn_starts_lifelong_history(
    tmp_path: Path,
) -> None:
    net = _Net(tmp_path)
    try:
        net.profiles.register_app(
            app_id="doctor_sv",
            display_name="Doctor SV",
            scopes=("display_name",),
        )
        net.profiles.register_app(
            app_id="escuela_sv",
            display_name="Escuela SV",
            scopes=("display_name",),
        )
        child = (
            net.identity.register_identity(
                kind=IdentityKind.PERSON,
                display_name="bebe",
                actor="doctor_sv",
            )
        )
        first = net.history.append(
            zid=child.zid,
            entry_type="birth_registration",
            actor_app="doctor_sv",
            payload={
                "hospital": "San Salvador",
                "name": "Bebe Perez",
            },
        )
        assert first.entry_seq == 1
        assert (
            first.prev_hash == "GENESIS"
        )
        second = net.history.append(
            zid=child.zid,
            entry_type="education",
            actor_app="escuela_sv",
            payload={
                "school": "Centro Escolar",
                "grade": "1st",
            },
        )
        assert second.entry_seq == 2
        assert (
            second.prev_hash
            == first.content_hash
        )
        timeline = net.history.timeline(
            zid=child.zid
        )
        assert len(timeline) == 2
        assert (
            timeline[0].entry_type
            == "birth_registration"
        )
        assert (
            net.history.verify_chain(
                zid=child.zid
            )
            is True
        )
        net.telemetry.ingest_outbox(
            net.outbox
        )
        events = (
            net.telemetry.query_events(
                event_type=(
                    "network.history"
                    ".appended"
                )
            )
        )
        assert len(events) >= 2
    finally:
        net.close()


def test_unregistered_app_cannot_append(
    tmp_path: Path,
) -> None:
    net = _Net(tmp_path)
    try:
        child = (
            net.identity.register_identity(
                kind=IdentityKind.PERSON,
                display_name="x",
                actor="t",
            )
        )
        with pytest.raises(
            PermissionError
        ):
            net.history.append(
                zid=child.zid,
                entry_type="health",
                actor_app="malware",
                payload={"fake": True},
            )
        assert (
            net.history.timeline(
                zid=child.zid
            )
            == ()
        )
    finally:
        net.close()


def test_history_is_tamper_evident(
    tmp_path: Path,
) -> None:
    net = _Net(tmp_path)
    try:
        net.profiles.register_app(
            app_id="doctor_sv",
            display_name="Doctor SV",
            scopes=("display_name",),
        )
        person = (
            net.identity.register_identity(
                kind=IdentityKind.PERSON,
                display_name="p",
                actor="doctor_sv",
            )
        )
        net.history.append(
            zid=person.zid,
            entry_type="birth_registration",
            actor_app="doctor_sv",
            payload={"ok": 1},
        )
        net.history.append(
            zid=person.zid,
            entry_type="health",
            actor_app="doctor_sv",
            payload={
                "check": "vaccines"
            },
        )
        assert (
            net.history.verify_chain(
                zid=person.zid
            )
            is True
        )
        net.db.execute(
            "UPDATE life_history_entries"
            " SET payload = '{\"faked\":"
            " true}' WHERE entry_seq = 1"
        )
        assert (
            net.history.verify_chain(
                zid=person.zid
            )
            is False
        )
    finally:
        net.close()
