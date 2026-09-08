"""Durable rate store: immutable exact-decimal history.

Rates are stored as TEXT for exact Decimal round-trips.
Rows are immutable: a conflicting write under the same
(pair, source, as_at) is an integrity error, never a
silent overwrite.
"""
from __future__ import annotations

from decimal import Decimal

from shared_engines.common.clocks import Clock
from shared_engines.common.errors import IntegrityError
from shared_engines.currency.contracts import CurrencyPair, Quote
from shared_engines.storage.database import Database
from shared_engines.storage.migrations import (
    Migration,
    MigrationRunner,
)

RATES_MIGRATIONS = (
    Migration(
        1,
        "exchange_rates",
        (
            "CREATE TABLE exchange_rates ("
            " id INTEGER PRIMARY KEY AUTOINCREMENT,"
            " pair TEXT NOT NULL,"
            " rate TEXT NOT NULL,"
            " source TEXT NOT NULL,"
            " as_at REAL NOT NULL,"
            " fetched_at REAL NOT NULL,"
            " UNIQUE (pair, source, as_at))",
            "CREATE INDEX rates_pair_time"
            " ON exchange_rates (pair, as_at)",
        ),
    ),
)


class DurableRateStore:
    def __init__(self, db: Database, clock: Clock) -> None:
        self._db = db
        self._clock = clock
        MigrationRunner(
            db, "currency", RATES_MIGRATIONS
        ).run(clock)

    def save(self, quote: Quote) -> None:
        with self._db.transaction() as cursor:
            existing = cursor.execute(
                "SELECT rate FROM exchange_rates"
                " WHERE pair = ? AND source = ? AND as_at = ?",
                (
                    quote.pair.normalized,
                    quote.source,
                    quote.quoted_at,
                ),
            ).fetchone()
            if existing is not None:
                if str(existing["rate"]) != str(quote.rate):
                    raise IntegrityError(
                        "conflicting rate for identical"
                        " pair/source/timestamp"
                    )
                return
            cursor.execute(
                "INSERT INTO exchange_rates"
                " (pair, rate, source, as_at, fetched_at)"
                " VALUES (?, ?, ?, ?, ?)",
                (
                    quote.pair.normalized,
                    str(quote.rate),
                    quote.source,
                    quote.quoted_at,
                    self._clock.now(),
                ),
            )

    def latest(self, pair: CurrencyPair) -> Quote | None:
        row = self._db.query_one(
            "SELECT * FROM exchange_rates WHERE pair = ?"
            " ORDER BY as_at DESC LIMIT 1",
            (pair.normalized,),
        )
        if row is None:
            return None
        return self._quote_from_row(row)

    def as_of(
        self, pair: CurrencyPair, at: float
    ) -> Quote | None:
        row = self._db.query_one(
            "SELECT * FROM exchange_rates WHERE pair = ?"
            " AND as_at <= ? ORDER BY as_at DESC LIMIT 1",
            (pair.normalized, at),
        )
        if row is None:
            return None
        return self._quote_from_row(row)

    @staticmethod
    def _quote_from_row(row: object) -> Quote:
        if not hasattr(row, "__getitem__"):
            raise IntegrityError("invalid rate row type")
        normalized = str(row["pair"])
        parts = normalized.split("/", 1)
        if len(parts) != 2:
            raise IntegrityError("corrupt pair in rate row")
        rate = Decimal(str(row["rate"]))
        as_at = float(row["as_at"])
        return Quote(
            pair=CurrencyPair(parts[0], parts[1]),
            rate=rate,
            quoted_at=as_at,
            expires_at=as_at + 300.0,
            source=str(row["source"]),
        )
