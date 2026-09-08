"""Structured JSON logging with request correlation."""
from __future__ import annotations

import sqlite3
from dataclasses import dataclass
from typing import Final

from shared_engines.common.clocks import Clock
from shared_engines.common.errors import IntegrityError
from shared_engines.common.identifiers import new_id
from shared_engines.common.serialization import (
    canonical_json_dumps,
    canonical_json_loads,
)
from shared_engines.common.validation import (
    require_int_range,
    require_non_empty_str,
)
from shared_engines.storage.database import Database
from shared_engines.storage.migrations import (
    Migration,
    MigrationRunner,
)

LEVELS: Final[tuple[str, ...]] = (
    "DEBUG",
    "INFO",
    "WARNING",
    "ERROR",
)

LOGS_MIGRATIONS = (
    Migration(
        1,
        "structured_logs",
        (
            "CREATE TABLE structured_logs ("
            " log_id INTEGER PRIMARY KEY AUTOINCREMENT,"
            " level TEXT NOT NULL,"
            " component TEXT NOT NULL,"
            " message TEXT NOT NULL,"
            " correlation_id TEXT NOT NULL,"
            " detail TEXT NOT NULL,"
            " created_at REAL NOT NULL)",
            "CREATE INDEX logs_correlation"
            " ON structured_logs (correlation_id, created_at)",
            "CREATE INDEX logs_level_time"
            " ON structured_logs (level, created_at)",
        ),
    ),
)


@dataclass(frozen=True)
class LogRecord:
    log_id: int
    level: str
    component: str
    message: str
    correlation_id: str
    detail: dict[str, str]
    created_at: float


class CorrelationContext:
    """Per-operation correlation id generator/tracker."""

    def __init__(self) -> None:
        self._current: str | None = None

    def start(self) -> str:
        self._current = f"REQ-{new_id()}"
        return self._current

    @property
    def current(self) -> str:
        if self._current is None:
            return self.start()
        return self._current

    def clear(self) -> None:
        self._current = None


class StructuredLogger:
    """Durable structured logger with correlation + retention."""

    def __init__(self, db: Database, clock: Clock) -> None:
        self._db = db
        self._clock = clock
        MigrationRunner(
            db, "logs.structured", LOGS_MIGRATIONS
        ).run(clock)

    def log(
        self,
        *,
        level: str,
        component: str,
        message: str,
        correlation_id: str,
        detail: dict[str, str] | None = None,
    ) -> LogRecord:
        if level not in LEVELS:
            raise IntegrityError(
                f"invalid log level: {level}"
            )
        require_non_empty_str(component, "component")
        require_non_empty_str(message, "message")
        require_non_empty_str(correlation_id, "correlation_id")
        safe_detail: dict[str, str] = {
            str(k): str(v) for k, v in (detail or {}).items()
        }
        now = self._clock.now()
        with self._db.transaction() as cursor:
            cursor.execute(
                "INSERT INTO structured_logs"
                " (level, component, message,"
                "  correlation_id, detail, created_at)"
                " VALUES (?, ?, ?, ?, ?, ?)",
                (
                    level,
                    component,
                    message,
                    correlation_id,
                    canonical_json_dumps(safe_detail),
                    now,
                ),
            )
            row = cursor.execute(
                "SELECT * FROM structured_logs"
                " ORDER BY log_id DESC LIMIT 1"
            ).fetchone()
        if row is None:
            raise IntegrityError("log vanished after insert")
        return self._record_from_row(row)

    def info(
        self,
        component: str,
        message: str,
        correlation_id: str,
        detail: dict[str, str] | None = None,
    ) -> LogRecord:
        return self.log(
            level="INFO",
            component=component,
            message=message,
            correlation_id=correlation_id,
            detail=detail,
        )

    def warning(
        self,
        component: str,
        message: str,
        correlation_id: str,
        detail: dict[str, str] | None = None,
    ) -> LogRecord:
        return self.log(
            level="WARNING",
            component=component,
            message=message,
            correlation_id=correlation_id,
            detail=detail,
        )

    def error(
        self,
        component: str,
        message: str,
        correlation_id: str,
        detail: dict[str, str] | None = None,
    ) -> LogRecord:
        return self.log(
            level="ERROR",
            component=component,
            message=message,
            correlation_id=correlation_id,
            detail=detail,
        )

    def query_by_correlation(
        self, correlation_id: str
    ) -> tuple[LogRecord, ...]:
        require_non_empty_str(correlation_id, "correlation_id")
        rows = self._db.query_all(
            "SELECT * FROM structured_logs"
            " WHERE correlation_id = ?"
            " ORDER BY created_at, log_id",
            (correlation_id,),
        )
        return tuple(self._record_from_row(r) for r in rows)

    def enforce_retention(self, *, keep: int) -> int:
        require_int_range(keep, "keep", 1, 1_000_000)
        with self._db.transaction() as cursor:
            cursor.execute(
                "DELETE FROM structured_logs"
                " WHERE log_id NOT IN"
                " (SELECT log_id FROM structured_logs"
                "  ORDER BY log_id DESC LIMIT ?)",
                (keep,),
            )
            row = cursor.execute(
                "SELECT changes()"
            ).fetchone()
        return int(row[0]) if row is not None else 0

    @staticmethod
    def _record_from_row(row: sqlite3.Row) -> LogRecord:
        detail_raw = canonical_json_loads(str(row["detail"]))
        if not isinstance(detail_raw, dict):
            detail_raw = {}
        detail: dict[str, str] = {
            str(k): str(v) for k, v in detail_raw.items()
        }
        return LogRecord(
            log_id=int(row["log_id"]),
            level=str(row["level"]),
            component=str(row["component"]),
            message=str(row["message"]),
            correlation_id=str(row["correlation_id"]),
            detail=detail,
            created_at=float(row["created_at"]),
        )
