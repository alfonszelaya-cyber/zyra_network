"""CLI: first-time installation of the Zyra Network.

Idempotent: on an existing healthy installation it
verifies and exits 0 without touching data.
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
    data.mkdir(parents=True, exist_ok=True)
    db_path = data / "zyra.db"
    if db_path.exists():
        try:
            adapter = SQLiteAdapter(db_path)
            try:
                adapter.integrity_check()
            finally:
                adapter.close()
        except Exception as exc:
            print(
                "install: existing database"
                f" is unhealthy: {exc}"
            )
            return 1
        print(
            "install: existing installation"
            " verified"
        )
        return 0
    adapter = SQLiteAdapter(db_path)
    try:
        report = NetworkMigrationRunner(
            adapter, SystemClock()
        ).run_all()
        print(
            f"install: migrated"
            f" {report.total_applied_now}"
            " across"
            f" {len(report.results)}"
            " namespaces"
        )
        manager = SnapshotManager(
            adapter,
            SystemClock(),
            Path(snapshot_dir),
        )
        snapshot = manager.create(
            label="install"
        )
        print(
            "install: baseline snapshot"
            f" {snapshot.path}"
        )
    finally:
        adapter.close()
    return 0


def main() -> None:
    parser = argparse.ArgumentParser(
        description=(
            "Install the Zyra Network"
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
