from __future__ import annotations

import hashlib
import os
import tempfile
from pathlib import Path
from threading import RLock


class StorageError(RuntimeError):
    """Raised for infrastructure storage failures."""


class StorageAdapter:
    """
    Durable filesystem storage boundary.

    Writes use a temporary file, fsync and atomic replace.
    """

    def __init__(
        self,
        root: str | Path,
    ) -> None:

        self.root = Path(
            root
        ).expanduser().resolve()

        self.root.mkdir(
            parents=True,
            exist_ok=True,
        )

        self._lock = RLock()
        self._closed = False

    def _require_open(self) -> None:
        if self._closed:
            raise StorageError(
                "Storage adapter is closed"
            )

    def _safe_path(
        self,
        relative_path: str | Path,
    ) -> Path:

        path = (
            self.root
            / Path(relative_path)
        ).resolve()

        try:
            path.relative_to(
                self.root
            )
        except ValueError as exc:
            raise StorageError(
                "Storage path escapes storage root"
            ) from exc

        return path

    def write_bytes(
        self,
        relative_path: str | Path,
        data: bytes,
    ) -> str:

        if not isinstance(data, bytes):
            raise TypeError(
                "Storage data must be bytes"
            )

        with self._lock:
            self._require_open()

            destination = self._safe_path(
                relative_path
            )

            destination.parent.mkdir(
                parents=True,
                exist_ok=True,
            )

            temporary_path: str | None = None

            try:
                with tempfile.NamedTemporaryFile(
                    mode="wb",
                    dir=destination.parent,
                    prefix=".zyra-",
                    suffix=".tmp",
                    delete=False,
                ) as temporary:

                    temporary.write(data)
                    temporary.flush()

                    os.fsync(
                        temporary.fileno()
                    )

                    temporary_path = (
                        temporary.name
                    )

                os.replace(
                    temporary_path,
                    destination,
                )

                return hashlib.sha256(
                    data
                ).hexdigest()

            except OSError as exc:
                if temporary_path:
                    try:
                        os.unlink(
                            temporary_path
                        )
                    except OSError:
                        pass

                raise StorageError(
                    "Atomic storage write failed"
                ) from exc

    def read_bytes(
        self,
        relative_path: str | Path,
    ) -> bytes:

        with self._lock:
            self._require_open()

            path = self._safe_path(
                relative_path
            )

            try:
                return path.read_bytes()
            except FileNotFoundError as exc:
                raise StorageError(
                    "Storage object not found"
                ) from exc
            except OSError as exc:
                raise StorageError(
                    "Storage read failed"
                ) from exc

    def exists(
        self,
        relative_path: str | Path,
    ) -> bool:

        with self._lock:
            self._require_open()

            return self._safe_path(
                relative_path
            ).is_file()

    def delete(
        self,
        relative_path: str | Path,
    ) -> bool:

        with self._lock:
            self._require_open()

            path = self._safe_path(
                relative_path
            )

            try:
                path.unlink()
                return True
            except FileNotFoundError:
                return False
            except OSError as exc:
                raise StorageError(
                    "Storage delete failed"
                ) from exc

    def checksum(
        self,
        relative_path: str | Path,
    ) -> str:

        return hashlib.sha256(
            self.read_bytes(
                relative_path
            )
        ).hexdigest()

    def list(
        self,
        prefix: str | Path = "",
    ) -> tuple[str, ...]:

        with self._lock:
            self._require_open()

            base = self._safe_path(
                prefix
            )

            if not base.exists():
                return ()

            if not base.is_dir():
                raise StorageError(
                    "Storage prefix is not a directory"
                )

            files = [
                path
                for path in base.rglob("*")
                if path.is_file()
            ]

            return tuple(
                sorted(
                    str(
                        path.relative_to(
                            self.root
                        )
                    )
                    for path in files
                )
            )

    def close(self) -> None:
        with self._lock:
            self._closed = True

    @property
    def closed(self) -> bool:
        with self._lock:
            return self._closed


__all__ = [
    "StorageAdapter",
    "StorageError",
]
