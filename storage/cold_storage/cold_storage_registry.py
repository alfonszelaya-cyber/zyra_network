from __future__ import annotations

from dataclasses import dataclass
from threading import RLock
from uuid import UUID


@dataclass(frozen=True, slots=True)
class StorageRecord:
    object_id: UUID
    key: str
    size_bytes: int
    location: str

    def __post_init__(self) -> None:
        if not self.key.strip():
            raise ValueError(
                "Storage record key cannot be empty"
            )

        if self.size_bytes < 0:
            raise ValueError(
                "Storage record size cannot be negative"
            )


class ColdStorageRegistry:
    def __init__(self) -> None:
        self._records: dict[
            str,
            StorageRecord,
        ] = {}

        self._lock = RLock()

    def register(
        self,
        record: StorageRecord,
        *,
        replace: bool = False,
    ) -> None:

        key = record.key.strip()

        with self._lock:
            if (
                key in self._records
                and not replace
            ):
                raise ValueError(
                    f"Storage record already exists: {key}"
                )

            self._records[key] = record

    def get(
        self,
        key: str,
    ) -> StorageRecord:

        with self._lock:
            try:
                return self._records[
                    key.strip()
                ]
            except KeyError as exc:
                raise LookupError(
                    f"Storage record not found: {key}"
                ) from exc

    def remove(
        self,
        key: str,
    ) -> bool:

        with self._lock:
            return (
                self._records.pop(
                    key.strip(),
                    None,
                )
                is not None
            )

    def list(
        self,
    ) -> tuple[StorageRecord, ...]:

        with self._lock:
            return tuple(
                self._records[key]
                for key in sorted(
                    self._records
                )
            )


__all__ = [
    "StorageRecord",
    "ColdStorageRegistry",
]
