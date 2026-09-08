from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

import pytest

from shared_engines.audit.chain import AuditTrail
from shared_engines.common.clocks import FrozenClock
from shared_engines.common.errors import EngineError
from shared_engines.events.contracts import Event, EventCatalog
from shared_engines.events.outbox import Outbox
from shared_engines.identity.contracts import IdentityKind
from shared_engines.identity.engine import IdentityEngine
from shared_engines.logs.structured import StructuredLogger
from shared_engines.storage.database import SQLiteAdapter
from shared_engines.storage.disaster_recovery import (
    DisasterRecovery,
)
from shared_engines.storage.snapshots import SnapshotManager
from shared_engines.tokenization.engine import TokenEngine


class SimulatedCrash(Exception):
    """Local chaos injection."""


def test_concurrent_identity_and_token_writes(
    tmp_path: Path,
) -> None:
    db = SQLiteAdapter(tmp_path / "stress.db")
    clock = FrozenClock()
    audit = AuditTrail(db, clock)
    outbox = Outbox(db, clock)
    outbox.ensure_schema()
    catalog = EventCatalog()
    for event_type in (
        "identity.registered",
        "identity.status_changed",
        "token.earned",
    ):
        catalog.register(event_type)
    identity = IdentityEngine(
        db=db, clock=clock, audit=audit,
        outbox=outbox, catalog=catalog,
    )
    tokens = TokenEngine(
        db=db, clock=clock, audit=audit,
        outbox=outbox, catalog=catalog,
        identity=identity,
    )
    tokens.define_rule(activity="stress", amount=1)

    def worker(worker_index: int) -> int:
        created = 0
        for index in range(5):
            user = identity.register_identity(
                kind=IdentityKind.PERSON,
                display_name=f"w{worker_index}-{index}",
                actor="stress",
            )
            tokens.earn(
                subject_zid=user.zid,
                activity="stress",
                ref_type="stress",
                ref_id=str(index),
            )
            created += 1
        return created

    with ThreadPoolExecutor(max_workers=10) as pool:
        results = list(pool.map(worker, range(10)))
    assert sum(results) == 50
    assert tokens.invariant_check() is True
    assert audit.verify() >= 50
    db.close()


def test_outbox_survives_chaos_consumer(
    tmp_path: Path,
) -> None:
    db = SQLiteAdapter(tmp_path / "chaos.db")
    clock = FrozenClock()
    outbox = Outbox(db, clock)
    outbox.ensure_schema()
    catalog = EventCatalog()
    catalog.register("chaos.event")
    delivered: list[str] = []
    attempts: list[int] = [0]

    def chaotic_consumer(event: Event) -> None:
        attempts[0] += 1
        if attempts[0] % 3 == 0:
            raise SimulatedCrash("chaos strike")
        delivered.append(event.event_id)

    for index in range(200):
        event = catalog.build(
            "chaos.event",
            aggregate_id=f"agg-{index}",
            payload={"n": index},
            clock=clock,
        )
        outbox.enqueue(event)

    rounds = 0
    while outbox.pending() and rounds < 500:
        try:
            outbox.dispatch_pending(chaotic_consumer)
        except SimulatedCrash:
            pass
        rounds += 1
    assert len(delivered) == 200
    assert len(set(delivered)) == 200
    assert len(outbox.pending()) == 0
    db.close()


def test_storage_closed_mid_ops_typed_errors(
    tmp_path: Path,
) -> None:
    db = SQLiteAdapter(tmp_path / "ops.db")
    clock = FrozenClock()
    audit = AuditTrail(db, clock)
    outbox = Outbox(db, clock)
    outbox.ensure_schema()
    catalog = EventCatalog()
    catalog.register("identity.registered")
    catalog.register("identity.status_changed")
    identity = IdentityEngine(
        db=db, clock=clock, audit=audit,
        outbox=outbox, catalog=catalog,
    )
    identity.register_identity(
        kind=IdentityKind.PERSON,
        display_name="before-close",
        actor="test",
    )
    db.close()
    with pytest.raises(EngineError):
        identity.register_identity(
            kind=IdentityKind.PERSON,
            display_name="after-close",
            actor="test",
        )
    reopened = SQLiteAdapter(tmp_path / "ops.db")
    row = reopened.query_one(
        "SELECT COUNT(*) AS n FROM identities"
    )
    assert row is not None
    assert int(row["n"]) == 1
    reopened.close()


def test_snapshot_consistent_under_concurrent_writes(
    tmp_path: Path,
) -> None:
    db = SQLiteAdapter(tmp_path / "live.db")
    clock = FrozenClock()
    db.execute(
        "CREATE TABLE IF NOT EXISTS log_entries ("
        " id INTEGER PRIMARY KEY AUTOINCREMENT,"
        " payload TEXT NOT NULL)"
    )
    stop_flag: list[bool] = [False]

    def writer() -> None:
        index = 0
        while not stop_flag[0]:
            db.execute(
                "INSERT INTO log_entries (payload)"
                " VALUES (?)",
                (f"entry-{index}",),
            )
            index += 1

    with ThreadPoolExecutor(max_workers=2) as pool:
        future = pool.submit(writer)
        manager = SnapshotManager(
            db, clock, tmp_path / "snaps"
        )
        snapshots = [
            manager.create(label=f"mid-{i}")
            for i in range(3)
        ]
        stop_flag[0] = True
        future.result()
    for record in snapshots:
        assert manager.verify(record.path)
    replica = SQLiteAdapter(tmp_path / "r-mid-0.db")
    manager.restore(snapshots[0].path, tmp_path / "r-mid-0.db")
    row = replica.query_one(
        "SELECT COUNT(*) AS n FROM log_entries"
    )
    assert row is not None
    assert int(row["n"]) > 0
    replica.close()
    db.close()


def test_dr_drill_full_cycle(tmp_path: Path) -> None:
    db = SQLiteAdapter(tmp_path / "db.sqlite")
    dr = DisasterRecovery(
        db, FrozenClock(), tmp_path / "snaps"
    )
    report = dr.run_drill(rows=25)
    assert report.success is True
    assert report.rows_checked == 25
    db.close()


def test_migrations_recover_partial_schema(
    tmp_path: Path,
) -> None:
    db = SQLiteAdapter(tmp_path / "partial.db")
    from shared_engines.common.clocks import FrozenClock as FC
    from shared_engines.storage.network_migrations import (
        NetworkMigrationRunner,
    )

    runner = NetworkMigrationRunner(db, FC())
    report = runner.run_all()
    assert report.total_applied_now > 0
    report2 = runner.run_all()
    assert report2.total_applied_now == 0
    for result in report2.results:
        assert len(result.versions) > 0
    db.close()


def test_logs_correlate_under_concurrency(
    tmp_path: Path,
) -> None:
    db = SQLiteAdapter(tmp_path / "logs.db")
    clock = FrozenClock()
    logger = StructuredLogger(db, clock)

    def write_trace(trace_index: int) -> str:
        corr = f"REQ-{trace_index}"
        for line in range(4):
            logger.info(
                "component",
                f"trace {trace_index} line {line}",
                corr,
            )
            clock.advance(0.001)
        return corr

    with ThreadPoolExecutor(max_workers=5) as pool:
        correlations = list(pool.map(write_trace, range(20)))
    for corr in correlations[:5]:
        trace = logger.query_by_correlation(corr)
        assert len(trace) == 4
        assert all(
            r.correlation_id == corr for r in trace
        )
    db.close()


def test_torture_summary_all_engines_alive(
    tmp_path: Path,
) -> None:
    db = SQLiteAdapter(tmp_path / "all.db")
    clock = FrozenClock()
    audit = AuditTrail(db, clock)
    outbox = Outbox(db, clock)
    outbox.ensure_schema()
    catalog = EventCatalog()
    for event_type in (
        "identity.registered",
        "identity.status_changed",
    ):
        catalog.register(event_type)
    identity = IdentityEngine(
        db=db, clock=clock, audit=audit,
        outbox=outbox, catalog=catalog,
    )
    user = identity.register_identity(
        kind=IdentityKind.PERSON,
        display_name="survivor",
        actor="torture",
    )
    moved = identity.transition_identity(
        user.zid,
        __import__(
            "shared_engines.identity.contracts",
            fromlist=["IdentityStatus"],
        ).IdentityStatus.ACTIVE,
        actor="torture",
        reason="survived",
    )
    assert moved.status.value == "ACTIVE"
    assert audit.verify() >= 2
    assert db.ping() is True
    db.close()
