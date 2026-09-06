from __future__ import annotations

import sqlite3
from contextlib import contextmanager
from pathlib import Path
from threading import RLock
from typing import Iterator, Sequence


class DatabaseError(RuntimeError):
    """Raised for infrastructure database failures."""


class Transaction:
    """
    Explicit transaction boundary.

    The connection uses autocommit mode, therefore explicit
    BEGIN/COMMIT/ROLLBACK statements are used for transactions.
    """

    def __init__(
        self,
        connection: sqlite3.Connection,
        lock: RLock,
    ) -> None:
        self._connection = connection
        self._lock = lock
        self._entered = False

    def __enter__(
        self,
    ) -> sqlite3.Connection:

        self._lock.acquire()

        try:
            self._connection.execute(
                "BEGIN"
            )
            self._entered = True
            return self._connection
        except sqlite3.Error as exc:
            self._lock.release()

            raise DatabaseError(
                "Unable to begin transaction"
            ) from exc

    def __exit__(
        self,
        exc_type,
        exc_value,
        traceback,
    ) -> bool:

        try:
            if exc_type is None:
                self._connection.execute(
                    "COMMIT"
                )
            else:
                self._connection.execute(
                    "ROLLBACK"
                )
        except sqlite3.Error as exc:
            try:
                self._connection.execute(
                    "ROLLBACK"
                )
            except sqlite3.Error:
                pass

            raise DatabaseError(
                "Transaction finalization failed"
            ) from exc
        finally:
            self._entered = False
            self._lock.release()

        return False


class Database:
    """
    Durable SQLite infrastructure backend.

    SQLite remains isolated behind this adapter so higher
    layers do not depend directly on sqlite3.
    """

    def __init__(
        self,
        path: str | Path,
        *,
        timeout_seconds: int = 30,
        wal: bool = True,
    ) -> None:

        if timeout_seconds <= 0:
            raise ValueError(
                "timeout_seconds must be positive"
            )

        self.path = Path(
            path
        ).expanduser()

        if str(self.path) != ":memory:":
            self.path.parent.mkdir(
                parents=True,
                exist_ok=True,
            )

        self._timeout_seconds = (
            timeout_seconds
        )

        self._wal = wal
        self._lock = RLock()
        self._connection: (
            sqlite3.Connection | None
        ) = None
        self._closed = False

        self.open()

    def open(self) -> None:
        with self._lock:
            if self._closed:
                raise DatabaseError(
                    "Database is closed"
                )

            if self._connection is not None:
                return

            try:
                connection = sqlite3.connect(
                    str(self.path),
                    timeout=self._timeout_seconds,
                    isolation_level=None,
                    check_same_thread=False,
                )

                connection.row_factory = (
                    sqlite3.Row
                )

                connection.execute(
                    "PRAGMA foreign_keys = ON"
                )

                # SQLite does not support parameter
                # placeholders inside PRAGMA assignments.
                busy_timeout_ms = (
                    self._timeout_seconds * 1000
                )

                connection.execute(
                    f"PRAGMA busy_timeout = "
                    f"{busy_timeout_ms}"
                )

                if self._wal:
                    connection.execute(
                        "PRAGMA journal_mode = WAL"
                    )

                connection.execute(
                    "PRAGMA synchronous = NORMAL"
                )

                connection.execute(
                    "PRAGMA temp_store = MEMORY"
                )

                self._connection = connection

            except sqlite3.Error as exc:
                if self._connection is None:
                    try:
                        connection.close()
                    except (
                        UnboundLocalError,
                        sqlite3.Error,
                    ):
                        pass

                raise DatabaseError(
                    "Unable to open database"
                ) from exc

    def _require_connection(
        self,
    ) -> sqlite3.Connection:

        if self._closed:
            raise DatabaseError(
                "Database is closed"
            )

        if self._connection is None:
            raise DatabaseError(
                "Database is not open"
            )

        return self._connection

    def execute(
        self,
        sql: str,
        parameters: Sequence[object] = (),
    ) -> sqlite3.Cursor:

        if not sql.strip():
            raise ValueError(
                "SQL statement cannot be empty"
            )

        with self._lock:
            connection = (
                self._require_connection()
            )

            try:
                return connection.execute(
                    sql,
                    tuple(parameters),
                )
            except sqlite3.Error as exc:
                raise DatabaseError(
                    "Database execution failed"
                ) from exc

    def executemany(
        self,
        sql: str,
        parameter_sets: Sequence[
            Sequence[object]
        ],
    ) -> sqlite3.Cursor:

        if not sql.strip():
            raise ValueError(
                "SQL statement cannot be empty"
            )

        with self._lock:
            connection = (
                self._require_connection()
            )

            try:
                return connection.executemany(
                    sql,
                    [
                        tuple(values)
                        for values in parameter_sets
                    ],
                )
            except sqlite3.Error as exc:
                raise DatabaseError(
                    "Database batch execution failed"
                ) from exc

    def query(
        self,
        sql: str,
        parameters: Sequence[object] = (),
    ) -> list[sqlite3.Row]:

        cursor = self.execute(
            sql,
            parameters,
        )

        return cursor.fetchall()

    def query_one(
        self,
        sql: str,
        parameters: Sequence[object] = (),
    ) -> sqlite3.Row | None:

        cursor = self.execute(
            sql,
            parameters,
        )

        return cursor.fetchone()

    def transaction(self) -> Transaction:
        with self._lock:
            connection = (
                self._require_connection()
            )

        return Transaction(
            connection,
            self._lock,
        )

    def create_schema(
        self,
        statements: Sequence[str],
    ) -> None:

        with self.transaction() as connection:
            for statement in statements:
                if not statement.strip():
                    continue

                try:
                    connection.execute(
                        statement
                    )
                except sqlite3.Error as exc:
                    raise DatabaseError(
                        "Schema initialization failed"
                    ) from exc

    @contextmanager
    def connection(
        self,
    ) -> Iterator[sqlite3.Connection]:

        with self._lock:
            yield self._require_connection()

    def checkpoint(self) -> None:
        with self._lock:
            connection = (
                self._require_connection()
            )

            try:
                connection.execute(
                    "PRAGMA wal_checkpoint(PASSIVE)"
                )
            except sqlite3.Error as exc:
                raise DatabaseError(
                    "Database checkpoint failed"
                ) from exc

    def close(self) -> None:
        with self._lock:
            if self._closed:
                return

            connection = self._connection
            self._connection = None
            self._closed = True

            if connection is None:
                return

            try:
                connection.close()
            except sqlite3.Error as exc:
                raise DatabaseError(
                    "Database close failed"
                ) from exc

    @property
    def closed(self) -> bool:
        with self._lock:
            return self._closed


__all__ = [
    "Database",
    "DatabaseError",
    "Transaction",
]
