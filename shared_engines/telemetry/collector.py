"""Durable telemetry collector: metrics + event stream ingestion.

Metrics (counters/gauges/timers) persist per name+tags.
``ingest_outbox`` consumes the Network's event stream and
indexes it by type, aggregate and time — the operations
history a dashboard or external monitor would query.
"""
from __future__ import annotations

import sqlite3
from dataclasses import dataclass

from shared_engines.common.clocks import Clock
from shared_engines.common.errors import ValidationError
from shared_engines.common.serialization import (
    canonical_json_dumps,
    canonical_json_loads,
)
from shared_engines.common.validation import (
    require_int_range,
    require_non_empty_str,
    require_positive_number,
)
from shared_engines.events.outbox import Outbox
from shared_engines.storage.database import Database
from shared_engines.storage.migrations import (
    Migration,
    MigrationRunner,
)
from shared_engines.telemetry.errors import InvalidMetricError

TELEMETRY_MIGRATIONS = (
    Migration(
        1,
        "telemetry_metrics",
        (
            "CREATE TABLE telemetry_metrics ("
            " metric_id INTEGER PRIMARY KEY AUTOINCREMENT,"
            " name TEXT NOT NULL,"
            " kind TEXT NOT NULL,"
            " value REAL NOT NULL,"
            " tags TEXT NOT NULL,"
            " recorded_at REAL NOT NULL)",
            "CREATE INDEX telemetry_metrics_name_time"
            " ON telemetry_metrics (name, recorded_at)",
        ),
    ),
    Migration(
        2,
        "telemetry_events",
        (
            "CREATE TABLE telemetry_events ("
            " event_id TEXT PRIMARY KEY,"
            " event_type TEXT NOT NULL,"
            " aggregate_id TEXT NOT NULL,"
            " payload TEXT NOT NULL,"
            " occurred_at REAL NOT NULL)",
            "CREATE INDEX telemetry_events_type_time"
            " ON telemetry_events (event_type, occurred_at)",
            "CREATE INDEX telemetry_events_aggregate"
            " ON telemetry_events (aggregate_id, occurred_at)",
        ),
    ),
)


@dataclass(frozen=True)
class TelemetryRecord:
    metric_id: int
    name: str
    kind: str
    value: float
    tags: dict[str, str]
    recorded_at: float


class TelemetryCollector:
    """Durable metrics + event stream ingestion."""

    def __init__(self, db: Database, clock: Clock) -> None:
        self._db = db
        self._clock = clock
        MigrationRunner(
            db, "telemetry", TELEMETRY_MIGRATIONS
        ).run(clock)

    def counter(
        self,
        name: str,
        *,
        tags: dict[str, str] | None = None,
    ) -> None:
        self._record(name, kind="counter", value=1.0, tags=tags)

    def gauge(
        self,
        name: str,
        value: float,
        *,
        tags: dict[str, str] | None = None,
    ) -> None:
        try:
            require_positive_number(value, name)
        except ValidationError as exc:
            raise InvalidMetricError(str(exc)) from exc
        self._record(name, kind="gauge", value=value, tags=tags)

    def timer(
        self,
        name: str,
        seconds: float,
        *,
        tags: dict[str, str] | None = None,
    ) -> None:
        try:
            require_positive_number(seconds, "duration")
        except ValidationError as exc:
            raise InvalidMetricError(str(exc)) from exc
        self._record(
            name, kind="timer", value=seconds, tags=tags
        )

    def _record(
        self,
        name: str,
        *,
        kind: str,
        value: float,
        tags: dict[str, str] | None,
    ) -> None:
        require_non_empty_str(name, "name")
        with self._db.transaction() as cursor:
            cursor.execute(
                "INSERT INTO telemetry_metrics"
                " (name, kind, value, tags, recorded_at)"
                " VALUES (?, ?, ?, ?, ?)",
                (
                    name,
                    kind,
                    value,
                    canonical_json_dumps(dict(tags or {})),
                    self._clock.now(),
                ),
            )

    def ingest_outbox(
        self, outbox: Outbox, *, batch_size: int = 100
    ) -> int:
        """Indexes pending outbox events into telemetry.

        Production pattern: telemetry ingests the Network's
        event stream. Events are marked published only after
        successful indexing, so a crash never loses events
        (at-least-once, deduped by event_id primary key).
        """
        require_int_range(batch_size, "batch_size", 1, 10_000)
        indexed = 0
        for event in outbox.pending(batch_size):
            try:
                with self._db.transaction() as cursor:
                    cursor.execute(
                        "INSERT INTO telemetry_events"
                        " (event_id, event_type, aggregate_id,"
                        "  payload, occurred_at)"
                        " VALUES (?, ?, ?, ?, ?)",
                        (
                            event.event_id,
                            event.event_type,
                            event.aggregate_id,
                            canonical_json_dumps(
                                dict(event.payload)
                            ),
                            event.timestamp,
                        ),
                    )
            except sqlite3.IntegrityError:
                pass
            outbox.dispatch_pending(
                lambda e: None, batch_size=1
            )
            indexed += 1
            if indexed >= batch_size:
                break
        return indexed

    def query_metrics(
        self,
        name: str,
        *,
        limit: int = 100,
    ) -> tuple[TelemetryRecord, ...]:
        require_non_empty_str(name, "name")
        require_int_range(limit, "limit", 1, 10_000)
        rows = self._db.query_all(
            "SELECT * FROM telemetry_metrics"
            " WHERE name = ?"
            " ORDER BY recorded_at DESC, metric_id DESC"
            " LIMIT ?",
            (name, limit),
        )
        return tuple(self._record_from_row(row) for row in rows)

    def query_events(
        self,
        *,
        event_type: str | None = None,
        aggregate_id: str | None = None,
        limit: int = 100,
    ) -> tuple[dict[str, object], ...]:
        require_int_range(limit, "limit", 1, 10_000)
        if event_type is not None and aggregate_id is not None:
            rows = self._db.query_all(
                "SELECT * FROM telemetry_events"
                " WHERE event_type = ? AND aggregate_id = ?"
                " ORDER BY occurred_at DESC LIMIT ?",
                (event_type, aggregate_id, limit),
            )
        elif event_type is not None:
            rows = self._db.query_all(
                "SELECT * FROM telemetry_events"
                " WHERE event_type = ?"
                " ORDER BY occurred_at DESC LIMIT ?",
                (event_type, limit),
            )
        elif aggregate_id is not None:
            rows = self._db.query_all(
                "SELECT * FROM telemetry_events"
                " WHERE aggregate_id = ?"
                " ORDER BY occurred_at DESC LIMIT ?",
                (aggregate_id, limit),
            )
        else:
            rows = self._db.query_all(
                "SELECT * FROM telemetry_events"
                " ORDER BY occurred_at DESC LIMIT ?",
                (limit,),
            )
        return tuple(
            {
                "event_id": str(row["event_id"]),
                "event_type": str(row["event_type"]),
                "aggregate_id": str(row["aggregate_id"]),
                "payload": canonical_json_loads(
                    str(row["payload"])
                ),
                "occurred_at": float(row["occurred_at"]),
            }
            for row in rows
        )

    def metric_summary(self, name: str) -> dict[str, object]:
        records = self.query_metrics(name, limit=10_000)
        if not records:
            return {
                "name": name,
                "count": 0,
                "total": 0.0,
                "last": None,
            }
        values = [r.value for r in records]
        return {
            "name": name,
            "count": len(values),
            "total": sum(values),
            "last": values[0],
        }

    @staticmethod
    def _record_from_row(row: sqlite3.Row) -> TelemetryRecord:
        tags = canonical_json_loads(str(row["tags"]))
        if not isinstance(tags, dict):
            tags = {}
        return TelemetryRecord(
            metric_id=int(row["metric_id"]),
            name=str(row["name"]),
            kind=str(row["kind"]),
            value=float(row["value"]),
            tags={str(k): str(v) for k, v in tags.items()},
            recorded_at=float(row["recorded_at"]),
        )
