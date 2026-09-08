"""CLI: full system diagnostics of the Zyra Network."""
from __future__ import annotations

import argparse
import json
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
    db_path = Path(data_dir) / "zyra.db"
    problems: list[str] = []
    report: dict[str, object] = {}
    if not db_path.exists():
        print(json.dumps(
            {"healthy": False,
             "problems": [f"no database at {db_path}"]},
            indent=2,
        ))
        return 1
    adapter = SQLiteAdapter(db_path)
    try:
        adapter.integrity_check()
        report["database_integrity"] = "ok"
    except Exception as exc:
        problems.append(f"integrity: {exc}")
    try:
        migration_report = (
            NetworkMigrationRunner(
                adapter, SystemClock()
            ).run_all()
        )
        report["migrations"] = {
            r.namespace: len(r.versions)
            for r in migration_report.results
        }
    except Exception as exc:
        problems.append(f"migrations: {exc}")
    try:
        manager = SnapshotManager(
            adapter, SystemClock(), Path(snapshot_dir)
        )
        snapshots = manager.list_snapshots()
        report["snapshots"] = {
            "count": len(snapshots),
            "latest": (
                snapshots[0].path.name
                if snapshots
                else None
            ),
        }
    except Exception as exc:
        problems.append(f"snapshots: {exc}")
    report["healthy"] = len(problems) == 0
    report["problems"] = problems
    print(json.dumps(report, indent=2))
    adapter.close()
    return 0 if not problems else 1


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Zyra Network diagnostics"
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
