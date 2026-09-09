"""Routing engine: the transversal route table.

Canonical layer mapping route keys to targets with
explicit priorities. Deliberately independent of
network/ (node-level routing) and currency (bridge
routing): this is the Network-wide registry for
"which target serves this key, in which order".

Resolution is deterministic: lowest priority
number wins, ties broken by route_id. Deactivating
a route falls resolution to the next one. Pure
utility layer.
"""
from __future__ import annotations

import sqlite3
from dataclasses import dataclass

from shared_engines.common.clocks import Clock
from shared_engines.common.errors import (
    NotFoundError,
)
from shared_engines.common.identifiers import (
    new_id,
)
from shared_engines.common.validation import (
    require_int_range,
    require_non_empty_str,
)
from shared_engines.routing.errors import (
    NoRouteError,
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
        "routing_routes",
        (
            "CREATE TABLE routing_routes ("
            " route_id TEXT PRIMARY KEY,"
            " route_key TEXT NOT NULL,"
            " target TEXT NOT NULL,"
            " priority INTEGER NOT NULL,"
            " active INTEGER NOT NULL"
            " DEFAULT 1,"
            " created_at REAL NOT NULL)",
            "CREATE INDEX routing_lookup"
            " ON routing_routes"
            " (route_key, priority,"
            " route_id)",
        ),
    ),
)


@dataclass(frozen=True)
class RouteRecord:
    route_id: str
    route_key: str
    target: str
    priority: int
    active: bool


class RoutingEngine:
    """Durable prioritized route table."""

    def __init__(
        self, db: Database, clock: Clock
    ) -> None:
        self._db = db
        self._clock = clock
        MigrationRunner(
            db, "routing", _MIGRATIONS
        ).run(clock)

    def _record(
        self, row: sqlite3.Row
    ) -> RouteRecord:
        return RouteRecord(
            route_id=str(
                row["route_id"]
            ),
            route_key=str(
                row["route_key"]
            ),
            target=str(row["target"]),
            priority=int(
                row["priority"]
            ),
            active=bool(
                int(row["active"])
            ),
        )

    def _by_id(
        self, route_id: str
    ) -> RouteRecord:
        row = self._db.query_one(
            "SELECT * FROM routing_routes"
            " WHERE route_id = ?",
            (route_id,),
        )
        if row is None:
            raise NotFoundError(
                "unknown route:"
                f" {route_id}"
            )
        return self._record(row)

    def register_route(
        self,
        *,
        route_key: str,
        target: str,
        priority: int = 100,
    ) -> RouteRecord:
        require_non_empty_str(
            route_key, "route_key"
        )
        require_non_empty_str(
            target, "target"
        )
        require_int_range(
            priority,
            "priority",
            1,
            10**6,
        )
        route_id = f"RTE-{new_id()}"
        with (
            self._db.transaction()
            as cursor
        ):
            cursor.execute(
                "INSERT INTO routing_routes"
                " (route_id, route_key,"
                "  target, priority,"
                "  active, created_at)"
                " VALUES (?, ?, ?, ?, 1, ?)",
                (
                    route_id,
                    route_key,
                    target,
                    priority,
                    self._clock.now(),
                ),
            )
        return self._by_id(route_id)

    def deactivate_route(
        self, *, route_id: str
    ) -> RouteRecord:
        require_non_empty_str(
            route_id, "route_id"
        )
        self._by_id(route_id)
        with (
            self._db.transaction()
            as cursor
        ):
            cursor.execute(
                "UPDATE routing_routes"
                " SET active = 0"
                " WHERE route_id = ?",
                (route_id,),
            )
        return self._by_id(route_id)

    def resolve(
        self, *, route_key: str
    ) -> RouteRecord:
        """Best active route: lowest priority
        number, tie by route_id."""
        require_non_empty_str(
            route_key, "route_key"
        )
        row = self._db.query_one(
            "SELECT * FROM routing_routes"
            " WHERE route_key = ?"
            " AND active = 1"
            " ORDER BY priority ASC,"
            " route_id ASC LIMIT 1",
            (route_key,),
        )
        if row is None:
            raise NoRouteError(
                "no active route for"
                f" '{route_key}'"
            )
        return self._record(row)

    def list_routes(
        self, *, route_key: str
    ) -> tuple[RouteRecord, ...]:
        require_non_empty_str(
            route_key, "route_key"
        )
        rows = self._db.query_all(
            "SELECT * FROM routing_routes"
            " WHERE route_key = ?"
            " ORDER BY priority ASC,"
            " route_id ASC",
            (route_key,),
        )
        return tuple(
            self._record(row)
            for row in rows
        )
