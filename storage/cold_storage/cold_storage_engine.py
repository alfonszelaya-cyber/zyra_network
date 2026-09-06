from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from threading import RLock
from typing import BinaryIO
from uuid import UUID, uuid4


@dataclass(frozen=True, slots=True)
class ColdObject:
    object_id: UUID
    key: str
    size_bytes: int
    created_at: datetime
    path: str

    def __post_init__(self) -> None:
        if not self.key.strip():
            raise ValueError(
                "Cold storage key cannot be empty"
            )

        if self.size_bytes < 0:
            raise ValueError(
                "Object size cannot be negative"
            )


class ColdStorageEngine:
    def __init__(
        self,
        root: str | Path,
    ) -> None:

        self.root = Path(root)
        self.root.mkdir(
            parents=True,
            exist_ok=True,
        )

        self._lock = RLock()

    def _safe_path(
        self,
        key: str,
    ) -> Path:

        normalized = key.strip().lstrip("/")

        if not normalized:
            raise ValueError(
                "Storage key cannot be empty"
            )

        path = (
            self.root / normalized
        ).resolve()

        root = self.root.resolve()

        if (
            path != root
            and root not in path.parents
        ):
            raise ValueError(
                "Storage key escapes storage root"
            )

        return path

    def put(
        self,
        key: str,
        data: bytes | bytearray | memoryview,
    ) -> ColdObject:

        payload = bytes(data)
        path = self._safe_path(key)

        with self._lock:
            path.parent.mkdir(
                parents=True,
                exist_ok=True,
            )

            path.write_bytes(payload)

            return ColdObject(
                object_id=uuid4(),
                key=key.strip().lstrip("/"),
                size_bytes=len(payload),
                created_at=datetime.now(
                    timezone.utc
                ),
                path=str(path),
            )

    def put_stream(
        self,
        key: str,
        stream: BinaryIO,
        *,
        chunk_size: int = 1024 * 1024,
    ) -> ColdObject:

        if chunk_size <= 0:
            raise ValueError(
                "chunk_size must be positive"
            )

        path = self._safe_path(key)

        total = 0

        with self._lock:
            path.parent.mkdir(
                parents=True,
                exist_ok=True,
            )

            with path.open("wb") as output:
                while True:
                    chunk = stream.read(
                        chunk_size
                    )

                    if not chunk:
                        break

                    output.write(chunk)
                    total += len(chunk)

        return ColdObject(
            object_id=uuid4(),
            key=key.strip().lstrip("/"),
            size_bytes=total,
            created_at=datetime.now(
                timezone.utc
            ),
            path=str(path),
        )

    def get(
        self,
        key: str,
    ) -> bytes:

        path = self._safe_path(key)

        with self._lock:
            if not path.is_file():
                raise FileNotFoundError(
                    f"Cold object not found: {key}"
                )

            return path.read_bytes()

    def exists(
        self,
        key: str,
    ) -> bool:

        return self._safe_path(
            key
        ).is_file()

    def delete(
        self,
        key: str,
    ) -> bool:

        path = self._safe_path(key)

        with self._lock:
            if not path.is_file():
                return False

            path.unlink()
            return True

    def size(
        self,
        key: str,
    ) -> int:

        path = self._safe_path(key)

        with self._lock:
            if not path.is_file():
                raise FileNotFoundError(
                    f"Cold object not found: {key}"
                )

            return path.stat().st_size


__all__ = [
    "ColdObject",
    "ColdStorageEngine",
]
