"""Operational scripts proofs: install (create +
idempotent), deploy (gate + validate), repair
(restore from snapshot after corruption), update
(idempotent migrations + post-update snapshot)."""
from __future__ import annotations

import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from scripts.backup import run as backup_run  # noqa: E402
from scripts.deploy import run as deploy_run  # noqa: E402
from scripts.install import run as install_run  # noqa: E402
from scripts.repair import run as repair_run  # noqa: E402
from scripts.update import run as update_run  # noqa: E402


def test_install_creates_then_idempotent(
    tmp_path: Path,
) -> None:
    data = tmp_path / "data"
    snaps = tmp_path / "snaps"
    assert (
        install_run(
            data_dir=data,
            snapshot_dir=snaps,
        )
        == 0
    )
    assert (data / "zyra.db").exists()
    baseline = list(
        snaps.glob("snapshot-*.db")
    )
    assert len(baseline) == 1
    assert (
        install_run(
            data_dir=data,
            snapshot_dir=snaps,
        )
        == 0
    )
    assert (
        len(list(snaps.glob("snapshot-*.db")))
        == 1
    )


def test_deploy_gates_and_validates(
    tmp_path: Path,
) -> None:
    data = tmp_path / "data"
    snaps = tmp_path / "snaps"
    assert (
        deploy_run(
            data_dir=data,
            snapshot_dir=snaps,
        )
        == 1
    )
    assert (
        install_run(
            data_dir=data,
            snapshot_dir=snaps,
        )
        == 0
    )
    assert (
        deploy_run(
            data_dir=data,
            snapshot_dir=snaps,
        )
        == 0
    )


def test_repair_restores_corrupted_db(
    tmp_path: Path,
) -> None:
    data = tmp_path / "data"
    snaps = tmp_path / "snaps"
    assert (
        install_run(
            data_dir=data,
            snapshot_dir=snaps,
        )
        == 0
    )
    assert (
        backup_run(
            data_dir=data,
            snapshot_dir=snaps,
            keep=5,
        )
        == 0
    )
    assert (
        repair_run(
            data_dir=data,
            snapshot_dir=snaps,
        )
        == 0
    )
    (data / "zyra.db").write_bytes(
        b"corrupted garbage bytes"
    )
    assert (
        repair_run(
            data_dir=data,
            snapshot_dir=snaps,
        )
        == 0
    )
    healthy = repair_run(
        data_dir=data,
        snapshot_dir=snaps,
    )
    assert healthy == 0


def test_update_applies_and_snapshots(
    tmp_path: Path,
) -> None:
    data = tmp_path / "data"
    snaps = tmp_path / "snaps"
    assert (
        update_run(
            data_dir=data,
            snapshot_dir=snaps,
        )
        == 1
    )
    assert (
        install_run(
            data_dir=data,
            snapshot_dir=snaps,
        )
        == 0
    )
    assert (
        update_run(
            data_dir=data,
            snapshot_dir=snaps,
        )
        == 0
    )
    assert (
        update_run(
            data_dir=data,
            snapshot_dir=snaps,
        )
        == 0
    )
    labels = [
        p.name
        for p in snaps.glob(
            "snapshot-*.db"
        )
    ]
    assert len(labels) >= 2
