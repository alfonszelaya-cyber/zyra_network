from __future__ import annotations

from dataclasses import dataclass

from .backup_engine import (
    BackupArtifact,
    BackupEngine,
)


@dataclass(frozen=True, slots=True)
class RestoreResult:
    backup_id: str
    bytes_restored: int


class RestoreEngine:
    def __init__(
        self,
        backup_engine: BackupEngine,
    ) -> None:

        self.backup_engine = backup_engine

    def restore(
        self,
        artifact: BackupArtifact,
        key: bytes,
    ) -> tuple[bytes, RestoreResult]:

        data = self.backup_engine.restore(
            artifact,
            key,
        )

        return data, RestoreResult(
            backup_id=str(
                artifact.backup_id
            ),
            bytes_restored=len(data),
        )


__all__ = [
    "RestoreEngine",
    "RestoreResult",
]
