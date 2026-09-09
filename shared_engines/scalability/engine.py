"""Scalability engine: capacity, backpressure,
deterministic partitioning.

- Capacity: bounded resources; admission refuses
  beyond the limit using the common BackpressureError.
- Partitioning: stable sha256-based keys, so an
  entity always maps to the same partition while
  spreading load evenly.

Pure utility layer for engines that need bounded
queues/shards; composition roots decide policy.
"""
from __future__ import annotations

import hashlib
from dataclasses import dataclass

from shared_engines.common.clocks import Clock
from shared_engines.common.errors import (
    BackpressureError,
)
from shared_engines.common.serialization import (
    canonical_json_dumps,
)
from shared_engines.common.validation import (
    require_int_range,
    require_non_empty_str,
)
from shared_engines.scalability.errors import (
    CapacityNotDefinedError,
)
from shared_engines.storage.database import (
    Database,
)
from shared_engines.storage.migrations import (
    Migration,
    MigrationRunner,
)

_MIGRATIONS = (
    Migration(
        1,
        "scalability_capacity",
        (
            "CREATE TABLE"
            " scalability_capacity ("
            " resource TEXT PRIMARY KEY,"
            " max_items INTEGER NOT NULL,"
            " used INTEGER NOT NULL,"
            " updated_at REAL NOT NULL)",
        ),
    ),
)


@dataclass(frozen=True)
class CapacityRecord:
    resource: str
    max_items: int
    used: int


class ScalabilityEngine:
    """Bounded resources + stable shards."""

    def __init__(
        self, db: Database, clock: Clock
    ) -> None:
        self._db = db
        self._clock = clock
        MigrationRunner(
            db,
            "scalability",
            _MIGRATIONS,
        ).run(clock)

    def define_capacity(
        self,
        *,
        resource: str,
        max_items: int,
    ) -> CapacityRecord:
        require_non_empty_str(
            resource, "resource"
        )
        require_int_range(
            max_items,
            "max_items",
            1,
            10**12,
        )
        with (
            self._db.transaction()
            as cursor
        ):
            cursor.execute(
                "INSERT INTO"
                " scalability_capacity"
                " (resource, max_items,"
                "  used, updated_at)"
                " VALUES (?, ?, 0, ?)"
                " ON CONFLICT(resource)"
                " DO UPDATE SET"
                " max_items ="
                " excluded.max_items,"
                " updated_at ="
                " excluded.updated_at",
                (
                    resource,
                    max_items,
                    self._clock.now(),
                ),
            )
        return self.usage(
            resource=resource
        )

    def _row(
        self, resource: str
    ) -> CapacityRecord:
        row = self._db.query_one(
            "SELECT * FROM"
            " scalability_capacity"
            " WHERE resource = ?",
            (resource,),
        )
        if row is None:
            raise (
                CapacityNotDefinedError(
                    "no capacity for"
                    f" '{resource}'"
                )
            )
        return CapacityRecord(
            resource=str(
                row["resource"]
            ),
            max_items=int(
                row["max_items"]
            ),
            used=int(row["used"]),
        )

    def admit(
        self,
        *,
        resource: str,
        requested: int = 1,
    ) -> CapacityRecord:
        """Take n slots or refuse with the
        common BackpressureError."""
        require_int_range(
            requested, "requested", 1, 10**9
        )
        current = self._row(resource)
        projected = (
            current.used + requested
        )
        if projected > current.max_items:
            raise BackpressureError(
                f"'{resource}' full:"
                f" {current.used}/"
                f"{current.max_items},"
                f" requested {requested}"
            )
        with (
            self._db.transaction()
            as cursor
        ):
            cursor.execute(
                "UPDATE"
                " scalability_capacity"
                " SET used = ?,"
                " updated_at = ?"
                " WHERE resource = ?"
                " AND used + ? <="
                " max_items",
                (
                    projected,
                    self._clock.now(),
                    resource,
                    requested,
                ),
            )
        return CapacityRecord(
            resource=resource,
            max_items=(
                current.max_items
            ),
            used=projected,
        )

    def release(
        self,
        *,
        resource: str,
        amount: int = 1,
    ) -> CapacityRecord:
        require_int_range(
            amount, "amount", 1, 10**9
        )
        current = self._row(resource)
        freed = max(
            0, current.used - amount
        )
        with (
            self._db.transaction()
            as cursor
        ):
            cursor.execute(
                "UPDATE"
                " scalability_capacity"
                " SET used = ?,"
                " updated_at = ?"
                " WHERE resource = ?",
                (
                    freed,
                    self._clock.now(),
                    resource,
                ),
            )
        return CapacityRecord(
            resource=resource,
            max_items=(
                current.max_items
            ),
            used=freed,
        )

    def usage(
        self, *, resource: str
    ) -> CapacityRecord:
        require_non_empty_str(
            resource, "resource"
        )
        return self._row(resource)

    @staticmethod
    def partition_key(
        *,
        entity_id: str,
        partitions: int,
    ) -> int:
        """Stable shard: same entity always
        maps to the same partition."""
        require_non_empty_str(
            entity_id, "entity_id"
        )
        require_int_range(
            partitions,
            "partitions",
            1,
            10_000,
        )
        digest = hashlib.sha256(
            canonical_json_dumps(
                {"e": entity_id}
            ).encode("utf-8")
        ).hexdigest()
        return int(digest, 16) % partitions
