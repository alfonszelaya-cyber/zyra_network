from __future__ import annotations

import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[3]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from scripts.backup import run as backup_run  # noqa: E402
from scripts.bootstrap import run as bootstrap_run  # noqa: E402
from scripts.cleanup import run as cleanup_run  # noqa: E402
from scripts.diagnostics import run as diagnostics_run  # noqa: E402
from scripts.migrate import run as migrate_run  # noqa: E402
from scripts.rollback import run as rollback_run  # noqa: E402
from scripts.verify_installation import (  # noqa: E402
    run as verify_run,
)
from shared_engines.storage.database import SQLiteAdapter  # noqa: E402


def test_full_ops_lifecycle(tmp_path: Path) -> None:
    data_dir = tmp_path / "data"
    snapshot_dir = tmp_path / "snaps"

    assert bootstrap_run(
        data_dir=data_dir, snapshot_dir=snapshot_dir
    ) == 0
    assert migrate_run(db_path=data_dir / "zyra.db") == 0
    assert verify_run(data_dir=data_dir) == 0
    adapter = SQLiteAdapter(data_dir / "zyra.db")
    adapter.execute("CREATE TABLE op_probe (id INTEGER)")
    adapter.close()
    assert backup_run(
        data_dir=data_dir,
        snapshot_dir=snapshot_dir,
        keep=5,
    ) == 0
    assert cleanup_run(
        data_dir=data_dir,
        snapshot_dir=snapshot_dir,
        keep_snapshots=5,
        keep_logs=100,
    ) == 0
    assert diagnostics_run(
        data_dir=data_dir, snapshot_dir=snapshot_dir
    ) == 0
    assert rollback_run(
        data_dir=data_dir, snapshot_dir=snapshot_dir
    ) == 0


def test_diagnostics_reports_missing_db(tmp_path: Path) -> None:
    code = diagnostics_run(
        data_dir=tmp_path / "empty",
        snapshot_dir=tmp_path / "snaps",
    )
    assert code == 1
