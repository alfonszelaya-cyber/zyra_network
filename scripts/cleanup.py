"""CLI: retention cleanup — snapshots + structured logs."""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from shared_engines.common.clocks import SystemClock  # noqa: E402
from shared_engines.logs.structured import StructuredLogger  # noqa: E402
from shared_engines.storage.database import SQLiteAdapter  # noqa: E402
from shared_engines.storage.snapshots import SnapshotManager  # noqa: E402


def run(
    *,
    data_dir: Path,
    snapshot_dir: Path,
    keep_snapshots: int,
    keep_logs: int,
) -> int:
    db_path = Path(data_dir) / "zyra.db"
    if not db_path.exists():
        print(f"no database at {db_path}")
        return 1
    adapter = SQLiteAdapter(db_path)
    manager = SnapshotManager(
        adapter, SystemClock(), Path(snapshot_dir)
    )
    removed_snapshots = manager.enforce_retention(
        keep=keep_snapshots
    )
    logger = StructuredLogger(adapter, SystemClock())
    removed_logs = logger.enforce_retention(keep=keep_logs)
    print(f"snapshots removed: {len(removed_snapshots)}")
    print(f"log records removed: {removed_logs}")
    adapter.close()
    return 0


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Zyra retention cleanup"
    )
    parser.add_argument("--data-dir", default="/tmp/zyra-data")
    parser.add_argument(
        "--snapshot-dir", default="/tmp/zyra-snapshots"
    )
    parser.add_argument("--keep-snapshots", type=int, default=10)
    parser.add_argument("--keep-logs", type=int, default=10_000)
    args = parser.parse_args()
    raise SystemExit(
        run(
            data_dir=Path(args.data_dir),
            snapshot_dir=Path(args.snapshot_dir),
            keep_snapshots=args.keep_snapshots,
            keep_logs=args.keep_logs,
        )
    )


if __name__ == "__main__":
    main()
