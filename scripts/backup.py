"""CLI: create a verified snapshot of the Zyra database."""
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


def run(*, data_dir: Path, snapshot_dir: Path, keep: int) -> int:
    db_path = Path(data_dir) / "zyra.db"
    if not db_path.exists():
        print(f"no database at {db_path}")
        return 1
    adapter = SQLiteAdapter(db_path)
    manager = SnapshotManager(
        adapter, SystemClock(), Path(snapshot_dir)
    )
    record = manager.create(label="scheduled")
    removed = manager.enforce_retention(keep=keep)
    print(f"snapshot: {record.path}")
    print(f"sha256: {record.sha256}")
    print(f"retention removed: {len(removed)}")
    adapter.close()
    return 0


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Zyra DB snapshot with retention"
    )
    parser.add_argument("--data-dir", default="/tmp/zyra-data")
    parser.add_argument(
        "--snapshot-dir", default="/tmp/zyra-snapshots"
    )
    parser.add_argument("--keep", type=int, default=10)
    args = parser.parse_args()
    raise SystemExit(
        run(
            data_dir=Path(args.data_dir),
            snapshot_dir=Path(args.snapshot_dir),
            keep=args.keep,
        )
    )


if __name__ == "__main__":
    main()
