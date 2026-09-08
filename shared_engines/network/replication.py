"""Hash-verified state replication between nodes.

Two layers:

1. Parity (legacy, preserved): ``compute_state_hash``
   and ``replicate`` verify that a replica's state
   hash matches the primary's.
2. Physical transfer (W4): ``export_state`` produces
   a self-describing snapshot (schema DDL + rows of
   the replicated tables), ``apply_state`` atomically
   replaces the destination tables with it, and
   ``replicate_to`` orchestrates transfer -> apply ->
   verify -> ack. Real rows move between two SQLite
   databases; deletes propagate; divergence is
   detected and healable by re-replicating.
"""
from __future__ import annotations

import json
from dataclasses import dataclass

from shared_engines.common.clocks import Clock
from shared_engines.common.identifiers import (
    stable_hash,
)
from shared_engines.common.validation import (
    require_non_empty_str,
)
from shared_engines.network.errors import (
    ReplicationMismatchError,
)
from shared_engines.storage.database import (
    Database,
)

REPLICATED_TABLES = (
    "identities",
    "cluster_nodes",
)


@dataclass(frozen=True)
class ReplicationReport:
    primary_node: str
    replica_node: str
    state_version: int
    state_hash: str
    consistent: bool
    rows_replicated: int


@dataclass(frozen=True)
class StateSnapshot:
    """Self-describing transferable state."""

    version: int
    state_hash: str
    schemas: dict[str, str]
    tables: dict[
        str, tuple[dict[str, object], ...]
    ]


class ReplicationManager:
    """Computes hashes, verifies parity and now also
    physically transfers state to replicas."""

    def __init__(
        self, db: Database, clock: Clock
    ) -> None:
        self._db = db
        self._clock = clock

    def compute_state_hash(
        self,
    ) -> tuple[int, str]:
        parts: list[str] = []
        for table in REPLICATED_TABLES:
            rows = self._db.query_all(
                f"SELECT * FROM {table}"
                " ORDER BY rowid"
            )
            for row in rows:
                parts.append(
                    json.dumps(
                        {
                            k: str(v)
                            for k, v in dict(
                                row
                            ).items()
                        },
                        sort_keys=True,
                    )
                )
        version = int(self._clock.now())
        return version, stable_hash(*parts)

    def export_state(self) -> StateSnapshot:
        """Capture schema DDL + rows + hash."""
        version, state_hash = (
            self.compute_state_hash()
        )
        tables: dict[
            str,
            tuple[dict[str, object], ...],
        ] = {}
        schemas: dict[str, str] = {}
        for table in REPLICATED_TABLES:
            rows = self._db.query_all(
                f"SELECT * FROM {table}"
                " ORDER BY rowid"
            )
            tables[table] = tuple(
                dict(row) for row in rows
            )
            schema_row = self._db.query_one(
                "SELECT sql FROM sqlite_master"
                " WHERE type = 'table'"
                " AND name = ?",
                (table,),
            )
            if schema_row is not None and (
                schema_row["sql"] is not None
            ):
                schemas[table] = str(
                    schema_row["sql"]
                )
        return StateSnapshot(
            version=version,
            state_hash=state_hash,
            schemas=schemas,
            tables=tables,
        )

    def apply_state(
        self, snapshot: StateSnapshot
    ) -> int:
        """Atomically replace local replicated
        tables with the snapshot. Returns the
        number of rows applied.

        FK-safe ordering: tables are created
        parent-first, emptied child-first and
        filled parent-first.
        """
        applied = 0
        with self._db.transaction() as cursor:
            for table in REPLICATED_TABLES:
                exists = cursor.execute(
                    "SELECT name FROM"
                    " sqlite_master"
                    " WHERE type = 'table'"
                    " AND name = ?",
                    (table,),
                ).fetchone()
                if exists is None:
                    ddl = (
                        snapshot.schemas.get(
                            table
                        )
                    )
                    if ddl:
                        cursor.execute(ddl)
            for table in reversed(
                REPLICATED_TABLES
            ):
                exists = cursor.execute(
                    "SELECT name FROM"
                    " sqlite_master"
                    " WHERE type = 'table'"
                    " AND name = ?",
                    (table,),
                ).fetchone()
                if exists is not None:
                    cursor.execute(
                        f"DELETE FROM {table}"
                    )
            for table in REPLICATED_TABLES:
                for row in (
                    snapshot.tables.get(
                        table, ()
                    )
                ):
                    cols = list(row.keys())
                    col_sql = ", ".join(cols)
                    marks = ", ".join(
                        "?" for _ in cols
                    )
                    cursor.execute(
                        f"INSERT INTO {table}"
                        f" ({col_sql}) VALUES"
                        f" ({marks})",
                        tuple(
                            row[c]
                            for c in cols
                        ),
                    )
                    applied += 1
        return applied

    def replicate_to(
        self,
        *,
        replica_db: Database,
        primary_node: str,
        replica_node: str,
    ) -> ReplicationReport:
        """Physical replication:
        transfer -> apply -> verify -> ack."""
        require_non_empty_str(
            primary_node, "primary_node"
        )
        require_non_empty_str(
            replica_node, "replica_node"
        )
        snapshot = self.export_state()
        replica_manager = ReplicationManager(
            replica_db, self._clock
        )
        applied = (
            replica_manager.apply_state(
                snapshot
            )
        )
        _, replica_hash = (
            replica_manager.compute_state_hash()
        )
        if replica_hash != snapshot.state_hash:
            raise ReplicationMismatchError(
                f"replica {replica_node} hash"
                f" {replica_hash[:16]} !="
                f" primary"
                f" {snapshot.state_hash[:16]}"
                " after apply"
            )
        return ReplicationReport(
            primary_node=primary_node,
            replica_node=replica_node,
            state_version=snapshot.version,
            state_hash=snapshot.state_hash,
            consistent=True,
            rows_replicated=applied,
        )

    def replicate(
        self,
        *,
        primary_node: str,
        replica_node: str,
        replica_hash: str | None = None,
        rows_replicated: int = 0,
    ) -> ReplicationReport:
        require_non_empty_str(
            primary_node, "primary_node"
        )
        require_non_empty_str(
            replica_node, "replica_node"
        )
        version, primary_hash = (
            self.compute_state_hash()
        )
        if replica_hash is None:
            replica_hash = primary_hash
        consistent = (
            replica_hash == primary_hash
        )
        if not consistent:
            raise ReplicationMismatchError(
                f"replica {replica_node} hash"
                f" {replica_hash[:16]}"
                f" != primary"
                f" {primary_hash[:16]}"
            )
        return ReplicationReport(
            primary_node=primary_node,
            replica_node=replica_node,
            state_version=version,
            state_hash=primary_hash,
            consistent=True,
            rows_replicated=rows_replicated,
        )
