from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from threading import RLock
from uuid import UUID


@dataclass(frozen=True, slots=True)
class BackupRecord:
    backup_id: UUID
    source: str
    path: str
    digest: str
    created_at: datetime

    def __post_init__(self) -> None:
        if not self.source.strip():
            raise ValueError(
                "Backup source cannot be empty"
            )

        if not self.digest.strip():
            raise ValueError(
                "Backup digest cannot be empty"
            )

        if self.created_at.tzinfo is None:
            raise ValueError(
                "created_at must be timezone-aware"
            )


class BackupRegistry:
    def __init__(self) -> None:
        self._records: dict[
            UUID,
            BackupRecord,
        ] = {}

        self._lock = RLock()

    def register(
        self,
        record: BackupRecord,
    ) -> None:

        with self._lock:
            if (
                record.backup_id
                in self._records
            ):
                raise ValueError(
                    "Backup already registered"
                )

            self._records[
                record.backup_id
            ] = record

    def get(
        self,
        backup_id: UUID,
    ) -> BackupRecord:

        with self._lock:
            try:
                return self._records[
                    backup_id
                ]
            except KeyError as exc:
                raise LookupError(
                    "Backup not found"
                ) from exc

    def remove(
        self,
        backup_id: UUID,
    ) -> bool:

        with self._lock:
            return (
                self._records.pop(
                    backup_id,
                    None,
                )
                is not None
            )

    def list(
        self,
    ) -> tuple[BackupRecord, ...]:

        with self._lock:
            return tuple(
                self._records.values()
            )


__all__ = [
    "BackupRecord",
    "BackupRegistry",
]
