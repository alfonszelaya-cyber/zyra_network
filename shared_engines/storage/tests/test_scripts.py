from __future__ import annotations

import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[3]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from scripts.backup import run as backup_run  # noqa: E402
from scripts.migrate import run as migrate_run  # noqa: E402
from shared_engines.storage.database import SQLiteAdapter  # noqa: E402


def test_backup_script_creates_snapshot(tmp_path: Path) -> None:
    data_dir = tmp_path / "data"
    data_dir.mkdir()
    adapter = SQLiteAdapter(data_dir / "zyra.db")
    adapter.execute("CREATE TABLE t (id INTEGER)")
    adapter.close()
    code = backup_run(
        data_dir=data_dir,
        snapshot_dir=tmp_path / "snaps",
        keep=3,
    )
    assert code == 0
    snaps = list((tmp_path / "snaps").glob("snapshot-*.db"))
    assert len(snaps) == 1


def test_backup_script_fails_without_db(
    tmp_path: Path,
) -> None:
    code = backup_run(
        data_dir=tmp_path / "empty",
        snapshot_dir=tmp_path / "snaps",
        keep=3,
    )
    assert code == 1


def test_migrate_script_migrates_full_network(
    tmp_path: Path,
) -> None:
    code = migrate_run(db_path=tmp_path / "net.db")
    assert code == 0
    code2 = migrate_run(db_path=tmp_path / "net.db")
    assert code2 == 0
