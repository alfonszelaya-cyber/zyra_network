"""CLI: initial bootstrap of the Zyra Network."""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from shared_engines.common.clocks import SystemClock  # noqa: E402
from shared_engines.storage.database import SQLiteAdapter  # noqa: E402
from shared_engines.storage.network_migrations import (  # noqa: E402
    NetworkMigrationRunner,
)
from shared_engines.storage.snapshots import SnapshotManager  # noqa: E402


def run(*, data_dir: Path, snapshot_dir: Path) -> int:
    Path(data_dir).mkdir(parents=True, exist_ok=True)
    db_path = Path(data_dir) / "zyra.db"
    adapter = SQLiteAdapter(db_path)
    report = NetworkMigrationRunner(
        adapter, SystemClock()
    ).run_all()
    print(
        f"migrated: {report.total_applied_now} applied,"
        f" {len(report.results)} namespaces"
    )
    manager = SnapshotManager(
        adapter, SystemClock(), Path(snapshot_dir)
    )
    snapshot = manager.create(label="bootstrap")
    print(f"bootstrap snapshot: {snapshot.path}")
    adapter.close()
    return 0


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Bootstrap the Zyra Network"
    )
    parser.add_argument("--data-dir", default="/tmp/zyra-data")
    parser.add_argument(
        "--snapshot-dir", default="/tmp/zyra-snapshots"
    )
    args = parser.parse_args()
    raise SystemExit(
        run(
            data_dir=Path(args.data_dir),
            snapshot_dir=Path(args.snapshot_dir),
        )
    )


if __name__ == "__main__":
    main()
