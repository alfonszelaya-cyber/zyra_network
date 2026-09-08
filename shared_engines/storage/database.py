"""SQLite persistence with explicit transaction semantics."""
from __future__ import annotations

import os
import sqlite3
import threading
from contextlib import (
    AbstractContextManager,
    contextmanager,
)
from pathlib import Path
from typing import (
    Any,
    Iterator,
    Protocol,
    Sequence,
)

from shared_engines.common.errors import (
    EngineError,
    IntegrityError,
)
from shared_engines.common.validation import (
    require_int_range,
)


class DatabaseClosedError(EngineError):
    """Operation attempted on a closed database."""


class Database(Protocol):
    """Minimal synchronous storage surface."""

    def execute(
        self, sql: str, params: Sequence[Any] = ()
    ) -> sqlite3.Cursor:
        ...

    def query_all(
        self, sql: str, params: Sequence[Any] = ()
    ) -> list[sqlite3.Row]:
        ...

    def query_one(
        self, sql: str, params: Sequence[Any] = ()
    ) -> sqlite3.Row | None:
        ...

    def transaction(
        self,
    ) -> AbstractContextManager[sqlite3.Cursor]:
        ...

    def ping(self) -> bool:
        ...

    def integrity_check(self) -> None:
        ...

    def close(self) -> None:
        ...


class SQLiteAdapter:
    """Thread-safe adapter with lifecycle guarantees.

    1. After ``close()`` every operation raises
       ``DatabaseClosedError`` (an ``EngineError``);
       raw sqlite3 errors never escape.
    2. If the file is replaced on disk (snapshot
       restore), the next operation detects the inode
       swap and transparently reopens, so adapters
       opened before the restore serve restored state.
    """

    def __init__(
        self,
        path: str | Path,
        *,
        busy_timeout_ms: int = 5000,
    ) -> None:
        require_int_range(
            busy_timeout_ms,
            "busy_timeout_ms",
            1,
            600_000,
            config=True,
        )
        target = Path(path)
        if str(target) != ":memory:":
            target.parent.mkdir(
                parents=True, exist_ok=True
            )
        self._lock = threading.RLock()
        self._closed = False
        self._file_path: Path | None = (
            None
            if str(target) == ":memory:"
            else target
        )
        self._identity: tuple[int, int] | None
        self._identity = None
        self._timeout_ms = int(busy_timeout_ms)
        self._conn = self._connect()
        self._mark_identity()

    def _connect(self) -> sqlite3.Connection:
        path_str = (
            ":memory:"
            if self._file_path is None
            else str(self._file_path)
        )
        conn = sqlite3.connect(
            path_str,
            timeout=self._timeout_ms / 1000.0,
            isolation_level=None,
            check_same_thread=False,
        )
        conn.row_factory = sqlite3.Row
        conn.execute("PRAGMA journal_mode=WAL")
        conn.execute("PRAGMA synchronous=FULL")
        conn.execute("PRAGMA foreign_keys=ON")
        conn.execute(
            "PRAGMA busy_timeout="
            f"{self._timeout_ms}"
        )
        return conn

    def _mark_identity(self) -> None:
        if self._file_path is None:
            self._identity = None
            return
        try:
            st = os.stat(self._file_path)
        except OSError:
            self._identity = None
            return
        self._identity = (st.st_dev, st.st_ino)

    def _reopen_if_swapped(self) -> None:
        if self._closed or self._file_path is None:
            return
        try:
            st = os.stat(self._file_path)
        except OSError:
            return
        if self._identity == (
            st.st_dev,
            st.st_ino,
        ):
            return
        self._conn.close()
        self._conn = self._connect()
        self._mark_identity()

    def _ensure_open(self) -> None:
        if self._closed:
            raise DatabaseClosedError(
                "database is closed:"
                " operation refused"
            )

    def execute(
        self, sql: str, params: Sequence[Any] = ()
    ) -> sqlite3.Cursor:
        with self._lock:
            self._ensure_open()
            self._reopen_if_swapped()
            return self._conn.execute(
                sql, tuple(params)
            )

    def query_all(
        self, sql: str, params: Sequence[Any] = ()
    ) -> list[sqlite3.Row]:
        with self._lock:
            self._ensure_open()
            self._reopen_if_swapped()
            rows: list[sqlite3.Row] = (
                self._conn.execute(
                    sql, tuple(params)
                ).fetchall()
            )
            return rows

    def query_one(
        self, sql: str, params: Sequence[Any] = ()
    ) -> sqlite3.Row | None:
        with self._lock:
            self._ensure_open()
            self._reopen_if_swapped()
            row: sqlite3.Row | None = (
                self._conn.execute(
                    sql, tuple(params)
                ).fetchone()
            )
            return row

    @contextmanager
    def transaction(
        self,
    ) -> Iterator[sqlite3.Cursor]:
        with self._lock:
            self._ensure_open()
            self._reopen_if_swapped()
            self._conn.execute("BEGIN IMMEDIATE")
            cursor = self._conn.cursor()
            try:
                yield cursor
            except BaseException:
                self._conn.execute("ROLLBACK")
                raise
            self._conn.execute("COMMIT")

    def ping(self) -> bool:
        try:
            with self._lock:
                if self._closed:
                    return False
                self._reopen_if_swapped()
                self._conn.execute(
                    "SELECT 1"
                ).fetchone()
        except sqlite3.Error:
            return False
        return True

    def integrity_check(self) -> None:
        row = self.query_one(
            "PRAGMA integrity_check"
        )
        result = (
            str(row[0])
            if row is not None
            else ""
        )
        if result != "ok":
            raise IntegrityError(
                "sqlite integrity check"
                f" failed: {result}"
            )

    def backup_to(self, destination: Path) -> None:
        """Consistent online backup (sqlite API)."""
        destination.parent.mkdir(
            parents=True, exist_ok=True
        )
        with self._lock:
            self._ensure_open()
            target = sqlite3.connect(
                str(destination)
            )
            try:
                self._conn.backup(target)
            finally:
                target.close()

    def close(self) -> None:
        with self._lock:
            if not self._closed:
                self._closed = True
                self._conn.close()
