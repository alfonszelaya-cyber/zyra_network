"""Reputation proofs: evidence-backed scoring,
self-rating refused, mixed signs, temporal decay,
evidence re-verification."""
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
from shared_engines.integrity.engine import (
    IntegrityEngine,
)
from shared_engines.reputation.engine import (
    ReputationEngine,
)
from shared_engines.reputation.errors import (
    EmptyEvidenceError,
    SelfReputationError,
    UnknownEntityError,
)
from shared_engines.reputation.policy import (
    ReputationPolicy,
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
            "reputation.event.recorded",
        ):
            self.catalog.register(et)
        self.identity = IdentityEngine(
            db=self.db,
            clock=self.clock,
            audit=self.audit,
            outbox=self.outbox,
            catalog=self.catalog,
        )
        self.integrity = IntegrityEngine(
            self.db, self.clock
        )
        self.telemetry = TelemetryCollector(
            self.db, self.clock
        )
        self.policy = ReputationPolicy(
            weight_per_event=10.0,
            half_life_seconds=100.0,
        )
        self.reputation = ReputationEngine(
            self.db,
            self.clock,
            identity=self.identity,
            integrity=self.integrity,
            audit=self.audit,
            outbox=self.outbox,
            policy=self.policy,
        )

    def person(
        self, name: str
    ) -> str:
        identity = (
            self.identity.register_identity(
                kind=(
                    IdentityKind.PERSON
                ),
                display_name=name,
                actor="bootstrap",
            )
        )
        return identity.zid

    def close(self) -> None:
        self.db.close()


def test_evidence_backed_score(
    tmp_path: Path,
) -> None:
    net = _Net(tmp_path)
    try:
        employer = net.person("employer")
        worker = net.person("worker")
        evidence = (
            b"contract 2026 signed"
        )
        event = net.reputation.record_event(
            subject_zid=worker,
            actor_zid=employer,
            kind="positive",
            evidence=evidence,
        )
        assert event.seq == 1
        summary = (
            net.reputation.summary(
                subject_zid=worker
            )
        )
        assert summary.score == 10
        assert (
            summary.positive_events == 1
        )
        assert (
            summary.negative_events == 0
        )
        assert (
            net.reputation.verify_evidence(
                event_id=event.event_id,
                evidence=evidence,
            )
            is True
        )
        assert (
            net.reputation.verify_evidence(
                event_id=event.event_id,
                evidence=b"faked",
            )
            is False
        )
        net.telemetry.ingest_outbox(
            net.outbox
        )
        events = (
            net.telemetry.query_events(
                event_type=(
                    "reputation.event"
                    ".recorded"
                )
            )
        )
        assert len(events) >= 1
    finally:
        net.close()


def test_self_rating_and_unknown_refused(
    tmp_path: Path,
) -> None:
    net = _Net(tmp_path)
    try:
        worker = net.person("worker")
        with pytest.raises(
            SelfReputationError
        ):
            net.reputation.record_event(
                subject_zid=worker,
                actor_zid=worker,
                kind="positive",
                evidence=b"self",
            )
        with pytest.raises(
            UnknownEntityError
        ):
            net.reputation.record_event(
                subject_zid=worker,
                actor_zid="ZID-ghost",
                kind="positive",
                evidence=b"e",
            )
        employer = net.person("employer")
        with pytest.raises(
            EmptyEvidenceError
        ):
            net.reputation.record_event(
                subject_zid=worker,
                actor_zid=employer,
                kind="positive",
                evidence=b"",
            )
        with pytest.raises(ValueError):
            net.reputation.record_event(
                subject_zid=worker,
                actor_zid=employer,
                kind="magical",
                evidence=b"e",
            )
        assert (
            net.reputation.summary(
                subject_zid=worker
            ).score
            == 0
        )
    finally:
        net.close()


def test_mixed_signs_cancel(
    tmp_path: Path,
) -> None:
    net = _Net(tmp_path)
    try:
        a = net.person("a")
        b = net.person("b")
        c = net.person("c")
        worker = net.person("worker")
        net.reputation.record_event(
            subject_zid=worker,
            actor_zid=a,
            kind="positive",
            evidence=b"good-1",
        )
        net.reputation.record_event(
            subject_zid=worker,
            actor_zid=b,
            kind="positive",
            evidence=b"good-2",
        )
        net.reputation.record_event(
            subject_zid=worker,
            actor_zid=c,
            kind="negative",
            evidence=b"breach",
        )
        summary = (
            net.reputation.summary(
                subject_zid=worker
            )
        )
        assert summary.score == 10
        assert (
            summary.positive_events == 2
        )
        assert (
            summary.negative_events == 1
        )
        assert (
            summary.last_event_at
            is not None
        )
    finally:
        net.close()


def test_decay_over_time(
    tmp_path: Path,
) -> None:
    net = _Net(tmp_path)
    try:
        employer = net.person("employer")
        worker = net.person("worker")
        net.reputation.record_event(
            subject_zid=worker,
            actor_zid=employer,
            kind="positive",
            evidence=b"fresh",
        )
        assert (
            net.reputation.score(
                subject_zid=worker
            )
            == 10
        )
        net.clock.advance(100)
        assert (
            net.reputation.score(
                subject_zid=worker
            )
            == 5
        )
        net.clock.advance(100)
        faded = net.reputation.score(
            subject_zid=worker
        )
        assert faded < 6
        assert faded >= 2
    finally:
        net.close()
