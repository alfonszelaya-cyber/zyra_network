"""Disaster recovery drill: prove backup->restore->verify."""
from __future__ import annotations

import sqlite3
from dataclasses import dataclass
from pathlib import Path

from shared_engines.common.clocks import Clock
from shared_engines.storage.database import SQLiteAdapter
from shared_engines.storage.snapshots import SnapshotManager


@dataclass(frozen=True)
class DrillReport:
    success: bool
    backup_path: Path
    restored_path: Path
    rows_checked: int
    detail: str


class DisasterRecovery:
    def __init__(
        self,
        adapter: SQLiteAdapter,
        clock: Clock,
        snapshot_dir: Path,
    ) -> None:
        self._adapter = adapter
        self._clock = clock
        self._snapshots = SnapshotManager(
            adapter, clock, snapshot_dir
        )

    def run_drill(self, *, rows: int = 5) -> DrillReport:
        self._adapter.execute(
            "DROP TABLE IF EXISTS dr_probe"
        )
        self._adapter.execute(
            "CREATE TABLE dr_probe (id INTEGER NOT NULL)"
        )
        for index in range(rows):
            self._adapter.execute(
                "INSERT INTO dr_probe (id) VALUES (?)",
                (index,),
            )
        snapshot = self._snapshots.create(label="dr-drill")
        self._adapter.execute("DELETE FROM dr_probe")
        restored = (
            self._snapshots._dir
            / f"restored-{snapshot.path.stem}.db"
        )
        self._snapshots.restore(snapshot.path, restored)
        connection = sqlite3.connect(
            f"file:{restored}?mode=ro", uri=True
        )
        try:
            row = connection.execute(
                "SELECT COUNT(*) FROM dr_probe"
            ).fetchone()
        finally:
            connection.close()
        count = int(row[0]) if row is not None else -1
        success = count == rows
        self._adapter.execute(
            "DROP TABLE IF EXISTS dr_probe"
        )
        return DrillReport(
            success=success,
            backup_path=snapshot.path,
            restored_path=restored,
            rows_checked=count,
            detail=(
                f"restored {count}/{rows} rows"
                + ("" if success else " MISMATCH")
            ),
        )
