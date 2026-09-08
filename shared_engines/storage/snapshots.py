"""Snapshot manager: labeled, verified, retention."""
from __future__ import annotations

import hashlib
import json
import os
import re
import sqlite3
from dataclasses import dataclass
from pathlib import Path

from shared_engines.common.clocks import Clock
from shared_engines.common.errors import (
    IntegrityError,
)
from shared_engines.common.identifiers import new_id
from shared_engines.storage.database import (
    SQLiteAdapter,
)


def _sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(
            lambda: handle.read(512 * 1024), b""
        ):
            digest.update(chunk)
    return digest.hexdigest()


@dataclass(frozen=True)
class SnapshotRecord:
    path: Path
    label: str
    created_at: float
    sha256: str
    size_bytes: int


class SnapshotManager:
    def __init__(
        self,
        adapter: SQLiteAdapter,
        clock: Clock,
        snapshot_dir: Path,
    ) -> None:
        self._adapter = adapter
        self._clock = clock
        self._dir = Path(snapshot_dir)
        self._dir.mkdir(
            parents=True, exist_ok=True
        )

    def _manifest(self, path: Path) -> Path:
        return path.with_suffix(
            ".manifest.json"
        )

    def create(
        self, *, label: str
    ) -> SnapshotRecord:
        safe = re.sub(
            r"[^a-z0-9_-]+", "-", label.lower()
        )
        safe = safe.strip("-") or "snap"
        stamp = (
            f"{int(self._clock.now())}-"
            f"{new_id()[:8]}"
        )
        path = self._dir / (
            f"snapshot-{stamp}-{safe}.db"
        )
        self._adapter.backup_to(path)
        digest = _sha256_file(path)
        created_at = self._clock.now()
        manifest: dict[str, object] = {
            "label": safe,
            "created_at": created_at,
            "sha256": digest,
        }
        self._manifest(path).write_text(
            json.dumps(manifest),
            encoding="utf-8",
        )
        self.verify(path)
        return SnapshotRecord(
            path=path,
            label=safe,
            created_at=created_at,
            sha256=digest,
            size_bytes=path.stat().st_size,
        )

    def verify(self, path: Path) -> str:
        if not path.exists():
            raise IntegrityError(
                f"snapshot missing: {path}"
            )
        manifest_path = self._manifest(path)
        if not manifest_path.exists():
            raise IntegrityError(
                "snapshot manifest missing:"
                f" {manifest_path}"
            )
        manifest = json.loads(
            manifest_path.read_text(
                encoding="utf-8"
            )
        )
        digest = _sha256_file(path)
        if not isinstance(manifest, dict) or (
            digest != manifest.get("sha256")
        ):
            raise IntegrityError(
                "snapshot hash does not match"
                " manifest"
            )
        connection = sqlite3.connect(
            f"file:{path}?mode=ro", uri=True
        )
        try:
            row = connection.execute(
                "PRAGMA integrity_check"
            ).fetchone()
        finally:
            connection.close()
        if row is None or str(row[0]) != "ok":
            raise IntegrityError(
                "snapshot failed"
                " integrity_check"
            )
        return digest

    def list_snapshots(
        self,
    ) -> tuple[SnapshotRecord, ...]:
        records: list[SnapshotRecord] = []
        for path in sorted(
            self._dir.glob("snapshot-*.db")
        ):
            manifest_path = self._manifest(path)
            if not manifest_path.exists():
                continue
            manifest = json.loads(
                manifest_path.read_text(
                    encoding="utf-8"
                )
            )
            if not isinstance(manifest, dict):
                continue
            records.append(
                SnapshotRecord(
                    path=path,
                    label=str(
                        manifest.get(
                            "label", ""
                        )
                    ),
                    created_at=float(
                        str(
                            manifest.get(
                                "created_at",
                                0.0,
                            )
                        )
                    ),
                    sha256=str(
                        manifest.get(
                            "sha256", ""
                        )
                    ),
                    size_bytes=(
                        path.stat().st_size
                    ),
                )
            )
        records.sort(
            key=lambda r: r.created_at,
            reverse=True,
        )
        return tuple(records)

    def enforce_retention(
        self, *, keep: int
    ) -> tuple[Path, ...]:
        if keep < 1:
            raise IntegrityError(
                "keep must be >= 1"
            )
        records = self.list_snapshots()
        removed: list[Path] = []
        for record in records[keep:]:
            record.path.unlink(missing_ok=True)
            self._manifest(
                record.path
            ).unlink(missing_ok=True)
            removed.append(record.path)
        return tuple(removed)

    def restore(
        self, path: Path, target: Path
    ) -> None:
        """Restore a verified snapshot.

        Durable swap: temp file, fsync, atomic
        replace. Open adapters detect the inode
        swap and transparently reopen.
        """
        self.verify(path)
        target.parent.mkdir(
            parents=True, exist_ok=True
        )
        for suffix in ("-wal", "-shm"):
            Path(
                str(target) + suffix
            ).unlink(missing_ok=True)
        tmp = target.with_name(
            f"{target.name}.restore-"
            f"{new_id()[:8]}"
        )
        with open(tmp, "wb") as handle:
            handle.write(path.read_bytes())
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(tmp, target)
