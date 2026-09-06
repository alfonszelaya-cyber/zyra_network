from __future__ import annotations

from dataclasses import dataclass
from threading import RLock

from .cold_storage_engine import (
    ColdObject,
    ColdStorageEngine,
)


@dataclass(frozen=True, slots=True)
class StorageOperation:
    operation: str
    key: str
    success: bool


class ColdStorageManager:
    def __init__(
        self,
        engine: ColdStorageEngine,
    ) -> None:

        self.engine = engine
        self._lock = RLock()

    def store(
        self,
        key: str,
        data: bytes,
    ) -> ColdObject:

        with self._lock:
            return self.engine.put(
                key,
                data,
            )

    def retrieve(
        self,
        key: str,
    ) -> bytes:

        with self._lock:
            return self.engine.get(key)

    def remove(
        self,
        key: str,
    ) -> StorageOperation:

        with self._lock:
            success = self.engine.delete(
                key
            )

            return StorageOperation(
                operation="delete",
                key=key,
                success=success,
            )

    def contains(
        self,
        key: str,
    ) -> bool:

        with self._lock:
            return self.engine.exists(
                key
            )


__all__ = [
    "StorageOperation",
    "ColdStorageManager",
]
