"""Concurrency proofs: exclusivity, fencing,
backoff, dead-letter, reaping, legacy dispatch."""
from __future__ import annotations

import hashlib
from pathlib import Path

from shared_engines.common.clocks import (
    FrozenClock,
)
from shared_engines.common.errors import (
    LeaseLost,
)
from shared_engines.common.serialization import (
    canonical_json_dumps,
)
from shared_engines.events.contracts import Event
from shared_engines.events.outbox import (
    Outbox,
    OutboxClaim,
)
from shared_engines.storage.database import (
    SQLiteAdapter,
)


def _make_event(
    suffix: str, ts: float
) -> Event:
    event_id = f"evt-{suffix}"
    event_type = "network.node.joined"
    aggregate_id = f"agg-{suffix}"
    payload: dict[str, object] = {
        "seq": suffix
    }
    fingerprint_src = canonical_json_dumps(
        {
            "event_id": event_id,
            "event_type": event_type,
            "aggregate_id": aggregate_id,
            "timestamp": ts,
            "payload": payload,
        }
    )
    fingerprint = hashlib.sha256(
        fingerprint_src.encode("utf-8")
    ).hexdigest()
    return Event(
        event_id=event_id,
        event_type=event_type,
        aggregate_id=aggregate_id,
        schema_version=1,
        envelope_version=1,
        timestamp=ts,
        payload=payload,
        fingerprint=fingerprint,
    )


def _boot(
    tmp_path: Path,
) -> tuple[
    SQLiteAdapter, Outbox, FrozenClock
]:
    db = SQLiteAdapter(
        tmp_path / "outbox.db"
    )
    clock = FrozenClock()
    outbox = Outbox(db, clock)
    outbox.ensure_schema()
    return db, outbox, clock


def test_two_workers_never_claim_same_event(
    tmp_path: Path,
) -> None:
    db, outbox, clock = _boot(tmp_path)
    try:
        for i in range(4):
            outbox.enqueue(
                _make_event(
                    str(i), clock.now()
                )
            )
        claims_a: tuple[
            OutboxClaim, ...
        ] = outbox.claim_batch(
            owner="worker-a",
            lease_seconds=30.0,
            limit=10,
        )
        claims_b: tuple[
            OutboxClaim, ...
        ] = outbox.claim_batch(
            owner="worker-b",
            lease_seconds=30.0,
            limit=10,
        )
        ids_a = {
            c.event.event_id
            for c in claims_a
        }
        ids_b = {
            c.event.event_id
            for c in claims_b
        }
        assert (
            len(claims_a) + len(claims_b)
            == 4
        )
        assert not (ids_a & ids_b)
    finally:
        db.close()


def test_complete_requires_owner_fencing(
    tmp_path: Path,
) -> None:
    db, outbox, clock = _boot(tmp_path)
    try:
        outbox.enqueue(
            _make_event("f1", clock.now())
        )
        (claim,) = outbox.claim_batch(
            owner="worker-a",
            lease_seconds=30.0,
        )
        try:
            outbox.complete(
                event_id=(
                    claim.event.event_id
                ),
                owner="worker-b",
                fencing_token=(
                    claim.fencing_token
                ),
            )
            raise AssertionError(
                "expected LeaseLost"
            )
        except LeaseLost:
            pass
        outbox.complete(
            event_id=claim.event.event_id,
            owner="worker-a",
            fencing_token=(
                claim.fencing_token
            ),
        )
        assert outbox.pending() == ()
    finally:
        db.close()


def test_fail_backoff_then_dead_letter(
    tmp_path: Path,
) -> None:
    db, outbox, clock = _boot(tmp_path)
    try:
        outbox.enqueue(
            _make_event("r1", clock.now())
        )
        (c1,) = outbox.claim_batch(
            owner="w", lease_seconds=30.0
        )
        scheduled = outbox.fail(
            event_id=c1.event.event_id,
            owner="w",
            fencing_token=(
                c1.fencing_token
            ),
            error="boom-1",
            max_attempts=2,
            backoff_base_seconds=1.0,
        )
        assert scheduled is True
        assert (
            outbox.claim_batch(
                owner="w",
                lease_seconds=30.0,
            )
            == ()
        )
        clock.advance(2)
        (c2,) = outbox.claim_batch(
            owner="w", lease_seconds=30.0
        )
        assert c2.fencing_token == 2
        dead = outbox.fail(
            event_id=c2.event.event_id,
            owner="w",
            fencing_token=(
                c2.fencing_token
            ),
            error="boom-2",
            max_attempts=2,
            backoff_base_seconds=1.0,
        )
        assert dead is False
        assert (
            len(outbox.dead_letter()) == 1
        )
        outbox.requeue_dead(
            event_id=c2.event.event_id
        )
        (c3,) = outbox.claim_batch(
            owner="w", lease_seconds=30.0
        )
        assert c3.fencing_token == 1
    finally:
        db.close()


def test_expired_lease_reaped_and_fenced(
    tmp_path: Path,
) -> None:
    db, outbox, clock = _boot(tmp_path)
    try:
        outbox.enqueue(
            _make_event("l1", clock.now())
        )
        (old,) = outbox.claim_batch(
            owner="worker-dead",
            lease_seconds=10.0,
        )
        clock.advance(11)
        assert (
            outbox.reap_expired_leases()
            == 1
        )
        (fresh,) = outbox.claim_batch(
            owner="worker-new",
            lease_seconds=30.0,
        )
        assert fresh.fencing_token == 2
        try:
            outbox.complete(
                event_id=(
                    fresh.event.event_id
                ),
                owner="worker-dead",
                fencing_token=(
                    old.fencing_token
                ),
            )
            raise AssertionError(
                "expected LeaseLost"
            )
        except LeaseLost:
            pass
        outbox.complete(
            event_id=fresh.event.event_id,
            owner="worker-new",
            fencing_token=(
                fresh.fencing_token
            ),
        )
        assert outbox.pending() == ()
    finally:
        db.close()


def test_legacy_dispatch_still_works(
    tmp_path: Path,
) -> None:
    db, outbox, clock = _boot(tmp_path)
    try:
        outbox.enqueue(
            _make_event("a", clock.now())
        )
        outbox.enqueue(
            _make_event("b", clock.now())
        )
        seen: list[str] = []

        def collect(
            event: Event,
        ) -> None:
            seen.append(event.event_id)

        delivered = (
            outbox.dispatch_pending(collect)
        )
        assert delivered == 2
        assert len(seen) == 2
        assert outbox.pending() == ()
    finally:
        db.close()
