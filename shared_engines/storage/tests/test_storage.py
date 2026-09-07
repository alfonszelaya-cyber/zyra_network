from __future__ import annotations

from pathlib import Path

import pytest

from shared_engines.common.clocks import FrozenClock
from shared_engines.common.errors import IntegrityError, MigrationError
from shared_engines.storage.backup import BackupManager
from shared_engines.storage.database import SQLiteAdapter
from shared_engines.storage.migrations import Migration, MigrationRunner


class SimulatedCrash(Exception):
    """Local failure to prove rollback."""


def _mig(version: int, name: str, sql: str) -> Migration:
    return Migration(version=version, name=name, statements=(sql,))


def test_migrations_apply_once(tmp_path: Path) -> None:
    adapter = SQLiteAdapter(tmp_path / "state.db")
    runner = MigrationRunner(
        adapter,
        "test",
        (
            _mig(1, "create", "CREATE TABLE t (id INTEGER)"),
            _mig(2, "seed", "INSERT INTO t (id) VALUES (1)"),
        ),
    )
    assert runner.run(FrozenClock()) == (1, 2)
    assert runner.run(FrozenClock()) == (1, 2)
    assert len(adapter.query_all("SELECT id FROM t")) == 1
    adapter.close()


def test_migration_checksum_tampering_detected(tmp_path: Path) -> None:
    adapter = SQLiteAdapter(tmp_path / "state.db")
    runner = MigrationRunner(
        adapter, "test", (_mig(1, "create", "CREATE TABLE t (id)"),)
    )
    runner.run(FrozenClock())
    adapter.execute(
        "UPDATE schema_migrations SET checksum = 'tampered'"
        " WHERE version = 1"
    )
    with pytest.raises(MigrationError):
        runner.run(FrozenClock())
    adapter.close()


def test_transaction_rollback_on_crash(tmp_path: Path) -> None:
    adapter = SQLiteAdapter(tmp_path / "state.db")
    adapter.execute("CREATE TABLE t (id INTEGER)")
    with pytest.raises(SimulatedCrash):
        with adapter.transaction() as cursor:
            cursor.execute("INSERT INTO t (id) VALUES (1)")
            raise SimulatedCrash("died mid-transaction")
    row = adapter.query_one("SELECT COUNT(*) AS n FROM t")
    assert row is not None
    assert int(row["n"]) == 0
    adapter.close()


def test_backup_verify_restore_and_tamper(tmp_path: Path) -> None:
    adapter = SQLiteAdapter(tmp_path / "live.db")
    adapter.execute("CREATE TABLE t (id INTEGER)")
    adapter.execute("INSERT INTO t (id) VALUES (42)")
    manager = BackupManager(adapter, FrozenClock())
    backup = manager.create_backup(tmp_path / "backups")
    assert len(manager.verify_backup(backup)) == 64
    restore_target = tmp_path / "restored.db"
    manager.restore(backup, restore_target)
    replica = SQLiteAdapter(restore_target)
    row = replica.query_one("SELECT id FROM t")
    assert row is not None
    assert int(row["id"]) == 42
    replica.close()
    backup.write_bytes(backup.read_bytes() + b"corruption")
    with pytest.raises(IntegrityError):
        manager.verify_backup(backup)
    adapter.close()


def test_backup_without_manifest_rejected(tmp_path: Path) -> None:
    adapter = SQLiteAdapter(tmp_path / "live.db")
    adapter.execute("CREATE TABLE t (id INTEGER)")
    manager = BackupManager(adapter, FrozenClock())
    backup = manager.create_backup(tmp_path / "backups")
    backup.with_suffix(".manifest.json").unlink()
    with pytest.raises(IntegrityError):
        manager.verify_backup(backup)
    adapter.close()
