"""Verified backup and restore.

A backup is valid only after its hash matches the manifest and
a fresh read-only connection passes integrity_check. Restore
swaps atomically and never trusts an unverified copy.
"""
from __future__ import annotations

import hashlib
import os
import sqlite3
from pathlib import Path

from shared_engines.common.clocks import Clock
from shared_engines.common.errors import IntegrityError
from shared_engines.common.identifiers import new_id
from shared_engines.common.serialization import (
    canonical_json_dumps,
    canonical_json_loads,
)
from shared_engines.storage.database import SQLiteAdapter


def _file_sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(512 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _manifest_path(backup_path: Path) -> Path:
    return backup_path.with_suffix(".manifest.json")


class BackupManager:
    def __init__(self, adapter: SQLiteAdapter, clock: Clock) -> None:
        self._adapter = adapter
        self._clock = clock

    def create_backup(self, target_dir: Path) -> Path:
        target_dir.mkdir(parents=True, exist_ok=True)
        stamp = f"{int(self._clock.now())}-{new_id()[:8]}"
        backup_path = target_dir / f"backup-{stamp}.db"
        self._adapter.backup_to(backup_path)
        manifest = {
            "created_at": self._clock.now(),
            "file": backup_path.name,
            "sha256": _file_sha256(backup_path),
        }
        _manifest_path(backup_path).write_text(
            canonical_json_dumps(manifest), encoding="utf-8"
        )
        self.verify_backup(backup_path)
        return backup_path

    def verify_backup(self, backup_path: Path) -> str:
        if not backup_path.exists():
            raise IntegrityError(f"backup file missing: {backup_path}")
        manifest_path = _manifest_path(backup_path)
        if not manifest_path.exists():
            raise IntegrityError(
                f"backup manifest missing: {manifest_path}"
            )
        manifest = canonical_json_loads(
            manifest_path.read_text(encoding="utf-8")
        )
        digest = _file_sha256(backup_path)
        if not isinstance(manifest, dict) or digest != manifest.get(
            "sha256"
        ):
            raise IntegrityError("backup hash does not match manifest")
        connection = sqlite3.connect(
            f"file:{backup_path}?mode=ro", uri=True
        )
        try:
            row = connection.execute(
                "PRAGMA integrity_check"
            ).fetchone()
        finally:
            connection.close()
        if row is None or str(row[0]) != "ok":
            raise IntegrityError("backup failed integrity_check")
        return digest

    def restore(self, backup_path: Path, target_path: Path) -> None:
        self.verify_backup(backup_path)
        target_path.parent.mkdir(parents=True, exist_ok=True)
        for suffix in ("-wal", "-shm"):
            Path(str(target_path) + suffix).unlink(missing_ok=True)
        tmp = target_path.with_name(
            f"{target_path.name}.restore-{new_id()[:8]}"
        )
        tmp.write_bytes(backup_path.read_bytes())
        os.replace(tmp, target_path)
