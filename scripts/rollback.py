"""CLI: rollback the database to the latest verified snapshot."""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from shared_engines.common.clocks import SystemClock  # noqa: E402
from shared_engines.storage.database import SQLiteAdapter  # noqa: E402
from shared_engines.storage.snapshots import SnapshotManager  # noqa: E402


def run(*, data_dir: Path, snapshot_dir: Path) -> int:
    db_path = Path(data_dir) / "zyra.db"
    if not db_path.exists():
        print(f"no database at {db_path}")
        return 1
    snapshots = sorted(
        Path(snapshot_dir).glob("snapshot-*.db"),
        key=lambda p: p.stat().st_mtime,
        reverse=True,
    )
    if not snapshots:
        print("no snapshots available for rollback")
        return 1
    latest = snapshots[0]
    adapter = SQLiteAdapter(db_path)
    manager = SnapshotManager(
        adapter, SystemClock(), Path(snapshot_dir)
    )
    manager.verify(latest)
    manager.restore(latest, db_path)
    print(f"rolled back to: {latest.name}")
    adapter.close()
    return 0


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Rollback to latest verified snapshot"
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
