"""CLI: pre-deployment validation and gating.

Verifies the installation is healthy and fully
migrated, then takes a pre-deploy snapshot so the
deployment has a rollback point.
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
from shared_engines.storage.network_migrations import (  # noqa: E402
    NetworkMigrationRunner,
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
            "deploy: no installation found"
            " at"
            f" {db_path}; run install first"
        )
        return 1
    adapter = SQLiteAdapter(db_path)
    try:
        adapter.integrity_check()
        report = NetworkMigrationRunner(
            adapter, SystemClock()
        ).run_all()
        print(
            "deploy: migrations applied"
            f" now: {report.total_applied_now}"
        )
        manager = SnapshotManager(
            adapter,
            SystemClock(),
            Path(snapshot_dir),
        )
        snapshot = manager.create(
            label="deploy"
        )
        print(
            "deploy: pre-deploy snapshot"
            f" {snapshot.path}"
        )
    except Exception as exc:
        print(
            f"deploy: validation failed:"
            f" {exc}"
        )
        return 1
    finally:
        adapter.close()
    print("deploy: ready")
    return 0


def main() -> None:
    parser = argparse.ArgumentParser(
        description=(
            "Validate and gate a deployment"
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
