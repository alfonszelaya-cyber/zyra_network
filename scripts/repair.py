"""CLI: database repair via verified snapshots.

Checks the installation's integrity; if the
database is unhealthy, restores the latest
verified snapshot and re-verifies. Healthy
databases are left untouched.
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from shared_engines.common.clocks import (  # noqa: E402
    SystemClock,
)
from shared_engines.storage.database import (  # noqa: E402
    SQLiteAdapter,
)
from shared_engines.storage.snapshots import (  # noqa: E402
    SnapshotManager,
)


def run(
    *,
    data_dir: Path,
    snapshot_dir: Path,
) -> int:
    data = Path(data_dir)
    db_path = data / "zyra.db"
    if not db_path.exists():
        print(
            "repair: nothing to repair"
            " (no database at"
            f" {db_path})"
        )
        return 1
    healthy = False
    failure: Exception | None = None
    try:
        adapter = SQLiteAdapter(db_path)
        try:
            adapter.integrity_check()
            healthy = True
        finally:
            adapter.close()
    except Exception as exc:
        failure = exc
        print(
            "repair: integrity check"
            f" failed: {exc}"
        )
    if healthy:
        print(
            "repair: database is healthy;"
            " no action taken"
        )
        return 0
    _ = failure
    snaps = sorted(
        Path(snapshot_dir).glob(
            "snapshot-*.db"
        ),
        reverse=True,
    )
    if not snaps:
        print(
            "repair: no snapshots"
            " available; cannot repair"
        )
        return 1
    latest = snaps[0]
    scratch = SQLiteAdapter(
        data / "repair-scratch.db"
    )
    try:
        manager = SnapshotManager(
            scratch,
            SystemClock(),
            Path(snapshot_dir),
        )
        manager.verify(latest)
        manager.restore(latest, db_path)
    except Exception as exc:
        print(
            "repair: restore failed:"
            f" {exc}"
        )
        return 1
    finally:
        scratch.close()
    (data / "repair-scratch.db").unlink(
        missing_ok=True
    )
    try:
        adapter = SQLiteAdapter(db_path)
        try:
            adapter.integrity_check()
        finally:
            adapter.close()
    except Exception as exc:
        print(
            "repair: post-restore check"
            f" failed: {exc}"
        )
        return 1
    print(
        "repair: restored from"
        f" {latest.name}; integrity ok"
    )
    return 0


def main() -> None:
    parser = argparse.ArgumentParser(
        description=(
            "Repair the Zyra database from"
            " snapshots"
        )
    )
    parser.add_argument(
        "--data-dir",
        default="/tmp/zyra-data",
    )
    parser.add_argument(
        "--snapshot-dir",
        default="/tmp/zyra-snapshots",
    )
    args = parser.parse_args()
    raise SystemExit(
        run(
            data_dir=Path(args.data_dir),
            snapshot_dir=Path(
                args.snapshot_dir
            ),
        )
    )


if __name__ == "__main__":
    main()
