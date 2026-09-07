"""Database protocol and the local durable SQLite adapter.

Domain logic depends on the ``Database`` protocol only. The
adapter enables WAL, FULL synchronous, foreign keys, busy
timeout and explicit transactions. It is NOT distributed HA;
future PostgreSQL adapters implement the same protocol.
"""
from __future__ import annotations

import sqlite3
import threading
from collections.abc import Iterator, Sequence
from contextlib import AbstractContextManager, contextmanager
from pathlib import Path
from typing import Any, Protocol

from shared_engines.common.errors import IntegrityError
from shared_engines.common.validation import require_int_range


class Database(Protocol):
    """Minimal synchronous storage surface used by all engines."""

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

    def transaction(self) -> AbstractContextManager[sqlite3.Cursor]:
        ...

    def ping(self) -> bool:
        ...

    def integrity_check(self) -> None:
        ...

    def close(self) -> None:
        ...


class SQLiteAdapter:
    """Thread-safe single-connection adapter, explicit transactions."""

    def __init__(
        self, path: str | Path, *, busy_timeout_ms: int = 5000
    ) -> None:
        require_int_range(
            busy_timeout_ms, "busy_timeout_ms", 1, 600_000, config=True
        )
        target = Path(path)
        if str(target) != ":memory:":
            target.parent.mkdir(parents=True, exist_ok=True)
        self._lock = threading.RLock()
        self._conn = sqlite3.connect(
            str(target),
            timeout=busy_timeout_ms / 1000.0,
            isolation_level=None,
            check_same_thread=False,
        )
        self._conn.row_factory = sqlite3.Row
        self._conn.execute("PRAGMA journal_mode=WAL")
        self._conn.execute("PRAGMA synchronous=FULL")
        self._conn.execute("PRAGMA foreign_keys=ON")
        self._conn.execute(f"PRAGMA busy_timeout={int(busy_timeout_ms)}")

    def execute(
        self, sql: str, params: Sequence[Any] = ()
    ) -> sqlite3.Cursor:
        with self._lock:
            return self._conn.execute(sql, tuple(params))

    def query_all(
        self, sql: str, params: Sequence[Any] = ()
    ) -> list[sqlite3.Row]:
        with self._lock:
            rows: list[sqlite3.Row] = self._conn.execute(
                sql, tuple(params)
            ).fetchall()
            return rows

    def query_one(
        self, sql: str, params: Sequence[Any] = ()
    ) -> sqlite3.Row | None:
        with self._lock:
            row: sqlite3.Row | None = self._conn.execute(
                sql, tuple(params)
            ).fetchone()
            return row

    @contextmanager
    def transaction(self) -> Iterator[sqlite3.Cursor]:
        with self._lock:
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
                self._conn.execute("SELECT 1").fetchone()
        except sqlite3.Error:
            return False
        return True

    def integrity_check(self) -> None:
        row = self.query_one("PRAGMA integrity_check")
        result = str(row[0]) if row is not None else ""
        if result != "ok":
            raise IntegrityError(
                f"sqlite integrity check failed: {result}"
            )

    def backup_to(self, destination: Path) -> None:
        """Consistent online backup via the sqlite backup API."""
        destination.parent.mkdir(parents=True, exist_ok=True)
        with self._lock:
            target = sqlite3.connect(str(destination))
            try:
                self._conn.backup(target)
            finally:
                target.close()

    def close(self) -> None:
        with self._lock:
            self._conn.close()
