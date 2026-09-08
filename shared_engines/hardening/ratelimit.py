"""Durable fixed-window rate limiter per API key."""
from __future__ import annotations

from dataclasses import dataclass
from typing import Final

from shared_engines.common.clocks import Clock
from shared_engines.common.validation import (
    require_int_range,
    require_non_empty_str,
)
from shared_engines.hardening.errors import RateLimitExceededError
from shared_engines.storage.database import Database
from shared_engines.storage.migrations import (
    Migration,
    MigrationRunner,
)

_SECONDS_PER_WINDOW: Final[int] = 3600

RATE_LIMIT_MIGRATIONS = (
    Migration(
        1,
        "rate_limit_windows",
        (
            "CREATE TABLE rate_limit_windows ("
            " key_id TEXT NOT NULL,"
            " window_start INTEGER NOT NULL,"
            " count INTEGER NOT NULL,"
            " PRIMARY KEY (key_id, window_start))",
        ),
    ),
)


@dataclass(frozen=True)
class RateCheckResult:
    allowed: bool
    remaining: int
    limit: int


class RateLimiter:
    """Fixed-window consumption counter per key (durable)."""

    def __init__(
        self,
        db: Database,
        clock: Clock,
        *,
        default_limit: int = 1000,
    ) -> None:
        require_int_range(
            default_limit,
            "default_limit",
            1,
            1_000_000,
            config=True,
        )
        self._db = db
        self._clock = clock
        self._default_limit = default_limit
        MigrationRunner(
            db, "hardening.ratelimit", RATE_LIMIT_MIGRATIONS
        ).run(clock)

    def check(
        self, key_id: str, *, limit: int | None = None
    ) -> RateCheckResult:
        """Checks and increments consumption atomically."""
        require_non_empty_str(key_id, "key_id")
        effective = (
            limit if limit is not None else self._default_limit
        )
        require_int_range(effective, "effective", 1, 1_000_000)
        now = self._clock.now()
        window = int(now // _SECONDS_PER_WINDOW)
        with self._db.transaction() as cursor:
            row = cursor.execute(
                "SELECT count FROM rate_limit_windows"
                " WHERE key_id = ? AND window_start = ?",
                (key_id, window),
            ).fetchone()
            current = int(row["count"]) if row is not None else 0
            if current >= effective:
                return RateCheckResult(
                    allowed=False,
                    remaining=0,
                    limit=effective,
                )
            cursor.execute(
                "INSERT INTO rate_limit_windows"
                " (key_id, window_start, count)"
                " VALUES (?, ?, 1)"
                " ON CONFLICT (key_id, window_start)"
                " DO UPDATE SET count = count + 1",
                (key_id, window),
            )
        return RateCheckResult(
            allowed=True,
            remaining=effective - current - 1,
            limit=effective,
        )

    def enforce(
        self, key_id: str, *, limit: int | None = None
    ) -> RateCheckResult:
        """check() that raises RateLimitExceededError."""
        result = self.check(key_id, limit=limit)
        if not result.allowed:
            raise RateLimitExceededError(
                f"rate limit {result.limit} exceeded for"
                f" {key_id}; try the next window"
            )
        return result
