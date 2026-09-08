"""Durable brute-force guard: temporary lockout after failures."""
from __future__ import annotations

from shared_engines.common.clocks import Clock
from shared_engines.common.errors import ConfigurationError
from shared_engines.common.validation import (
    require_int_range,
    require_non_empty_str,
)
from shared_engines.hardening.errors import SourceLockedError
from shared_engines.storage.database import Database
from shared_engines.storage.migrations import (
    Migration,
    MigrationRunner,
)

BRUTE_FORCE_MIGRATIONS = (
    Migration(
        1,
        "bruteforce_state",
        (
            "CREATE TABLE bruteforce_state ("
            " source TEXT PRIMARY KEY,"
            " failures INTEGER NOT NULL DEFAULT 0,"
            " locked_until REAL)",
        ),
    ),
)


class BruteForceGuard:
    """Tracks failed authentications per source and locks
    sources that exceed the threshold for a duration."""

    def __init__(
        self,
        db: Database,
        clock: Clock,
        *,
        max_failures: int = 5,
        lockout_seconds: float = 900.0,
    ) -> None:
        require_int_range(
            max_failures, "max_failures", 1, 100, config=True
        )
        if lockout_seconds <= 0:
            raise ConfigurationError(
                "lockout_seconds must be positive"
            )
        self._db = db
        self._clock = clock
        self._max_failures = max_failures
        self._lockout_seconds = lockout_seconds
        MigrationRunner(
            db, "hardening.bruteforce", BRUTE_FORCE_MIGRATIONS
        ).run(clock)

    def check_allowed(self, source: str) -> None:
        """Raises SourceLockedError if this source is locked."""
        require_non_empty_str(source, "source")
        row = self._db.query_one(
            "SELECT locked_until FROM bruteforce_state"
            " WHERE source = ?",
            (source,),
        )
        if row is None:
            return
        locked_until = row["locked_until"]
        if locked_until is None:
            return
        if self._clock.now() < float(locked_until):
            raise SourceLockedError(
                f"source {source} is locked due to failed"
                " authentication attempts"
            )
        self._db.execute(
            "DELETE FROM bruteforce_state WHERE source = ?",
            (source,),
        )

    def record_failure(self, source: str) -> bool:
        """Records a failure; returns True if now locked."""
        require_non_empty_str(source, "source")
        with self._db.transaction() as cursor:
            row = cursor.execute(
                "SELECT failures FROM bruteforce_state"
                " WHERE source = ?",
                (source,),
            ).fetchone()
            failures = (
                int(row["failures"]) if row is not None else 0
            )
            failures += 1
            locked = failures >= self._max_failures
            locked_until = (
                self._clock.now() + self._lockout_seconds
                if locked
                else None
            )
            cursor.execute(
                "INSERT INTO bruteforce_state"
                " (source, failures, locked_until)"
                " VALUES (?, ?, ?)"
                " ON CONFLICT (source) DO UPDATE SET"
                " failures = excluded.failures,"
                " locked_until = excluded.locked_until",
                (source, failures, locked_until),
            )
        return locked

    def reset(self, source: str) -> None:
        """Clears failures after a successful authentication."""
        require_non_empty_str(source, "source")
        self._db.execute(
            "DELETE FROM bruteforce_state WHERE source = ?",
            (source,),
        )
