from __future__ import annotations

from pathlib import Path

import pytest

from shared_engines.common.clocks import FrozenClock
from shared_engines.common.errors import IntegrityError
from shared_engines.storage.database import SQLiteAdapter
from shared_engines.storage.disaster_recovery import DisasterRecovery
from shared_engines.storage.network_migrations import (
    NetworkMigrationRunner,
)
from shared_engines.storage.snapshots import SnapshotManager


def test_network_migrations_apply_all_and_idempotent(
    tmp_path: Path,
) -> None:
    adapter = SQLiteAdapter(tmp_path / "net.db")
    runner = NetworkMigrationRunner(adapter, FrozenClock())
    report1 = runner.run_all()
    assert report1.total_applied_now > 0
    namespaces = {r.namespace for r in report1.results}
    assert {
        "audit",
        "identity",
        "tokenization",
        "hardening.keys",
    } <= namespaces
    report2 = runner.run_all()
    assert report2.total_applied_now == 0
    adapter.close()


def test_snapshot_create_list_verify(tmp_path: Path) -> None:
    adapter = SQLiteAdapter(tmp_path / "db.sqlite")
    adapter.execute("CREATE TABLE t (id INTEGER)")
    adapter.execute("INSERT INTO t (id) VALUES (1)")
    manager = SnapshotManager(
        adapter, FrozenClock(), tmp_path / "snaps"
    )
    record = manager.create(label="Nightly")
    assert record.label == "nightly"
    assert len(record.sha256) == 64
    assert len(manager.list_snapshots()) == 1
    adapter.close()
    assert manager.verify(record.path)
    with pytest.raises(IntegrityError):
        corrupt = record.path
        corrupt.write_bytes(corrupt.read_bytes() + b"x")
        manager.verify(corrupt)


def test_snapshot_retention_keeps_newest(tmp_path: Path) -> None:
    adapter = SQLiteAdapter(tmp_path / "db.sqlite")
    adapter.execute("CREATE TABLE t (id INTEGER)")
    manager = SnapshotManager(
        adapter, FrozenClock(), tmp_path / "snaps"
    )
    clock = FrozenClock()
    for _ in range(5):
        manager.create(label="cycle")
        clock.advance(10)
    removed = manager.enforce_retention(keep=2)
    assert len(removed) == 3
    assert len(manager.list_snapshots()) == 2
    adapter.close()


def test_snapshot_restore_recovers_data(tmp_path: Path) -> None:
    adapter = SQLiteAdapter(tmp_path / "db.sqlite")
    adapter.execute("CREATE TABLE t (id INTEGER)")
    adapter.execute("INSERT INTO t (id) VALUES (42)")
    manager = SnapshotManager(
        adapter, FrozenClock(), tmp_path / "snaps"
    )
    record = manager.create(label="pre-disaster")
    adapter.execute("DELETE FROM t")
    target = tmp_path / "restored.db"
    manager.restore(record.path, target)
    replica = SQLiteAdapter(target)
    row = replica.query_one("SELECT id FROM t")
    assert row is not None
    assert int(row["id"]) == 42
    replica.close()
    adapter.close()


def test_disaster_recovery_drill(tmp_path: Path) -> None:
    adapter = SQLiteAdapter(tmp_path / "db.sqlite")
    dr = DisasterRecovery(
        adapter, FrozenClock(), tmp_path / "snaps"
    )
    report = dr.run_drill(rows=5)
    assert report.success is True
    assert report.rows_checked == 5
    adapter.close()


def test_snapshot_without_manifest_rejected(
    tmp_path: Path,
) -> None:
    adapter = SQLiteAdapter(tmp_path / "db.sqlite")
    manager = SnapshotManager(
        adapter, FrozenClock(), tmp_path / "snaps"
    )
    record = manager.create(label="x")
    manager._manifest(record.path).unlink()
    with pytest.raises(IntegrityError):
        manager.verify(record.path)
    adapter.close()
