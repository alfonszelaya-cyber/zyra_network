"""CLI: verify the Zyra installation is complete and sane."""
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


def run(*, data_dir: Path) -> int:
    checks: dict[str, bool] = {}
    errors: list[str] = []
    for module in (
        "shared_engines.common.errors",
        "shared_engines.runtime.kernel",
        "shared_engines.identity.engine",
        "shared_engines.verification.engine",
        "shared_engines.tokenization.engine",
        "shared_engines.currency.engine",
        "shared_engines.hardening.api_keys",
        "shared_engines.authority.root",
    ):
        try:
            __import__(module)
            checks[module] = True
        except Exception as exc:
            checks[module] = False
            errors.append(f"{module}: {exc}")
    try:
        db_path = Path(data_dir) / "zyra.db"
        adapter = SQLiteAdapter(db_path)
        NetworkMigrationRunner(
            adapter, SystemClock()
        ).run_all()
        adapter.close()
        checks["database_migratable"] = True
    except Exception as exc:
        checks["database_migratable"] = False
        errors.append(f"database: {exc}")
    verified = not errors
    print(json.dumps(
        {"verified": verified, "checks": checks,
         "errors": errors},
        indent=2,
    ))
    return 0 if verified else 1


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Verify Zyra Network installation"
    )
    parser.add_argument("--data-dir", default="/tmp/zyra-data")
    args = parser.parse_args()
    raise SystemExit(run(data_dir=Path(args.data_dir)))


if __name__ == "__main__":
    main()
