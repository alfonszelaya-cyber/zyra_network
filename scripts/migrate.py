"""CLI: migrate the whole Network schema to the latest version."""
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


def run(*, db_path: Path) -> int:
    adapter = SQLiteAdapter(Path(db_path))
    report = NetworkMigrationRunner(
        adapter, SystemClock()
    ).run_all()
    for result in report.results:
        print(
            f"{result.namespace}: {len(result.versions)} versions"
            f" ({len(result.applied_now)} applied now)"
        )
    print(f"total applied now: {report.total_applied_now}")
    adapter.close()
    return 0


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Migrate the whole Zyra Network schema"
    )
    parser.add_argument(
        "--db", default="/tmp/zyra-data/zyra.db"
    )
    args = parser.parse_args()
    raise SystemExit(run(db_path=Path(args.db)))


if __name__ == "__main__":
    main()
