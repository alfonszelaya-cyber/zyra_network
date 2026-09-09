"""Interoperability engine: versioned schemas and
mutual-version negotiation."""
from __future__ import annotations

from dataclasses import dataclass

from shared_engines.common.clocks import Clock
from shared_engines.common.errors import (
    NotFoundError,
    UnsupportedVersionError,
)
from shared_engines.common.validation import (
    require_int_range,
    require_non_empty_str,
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
        "interoperability",
        (
            "CREATE TABLE interop_schemas ("
            " schema_id TEXT NOT NULL,"
            " version INTEGER NOT NULL,"
            " definition TEXT NOT NULL,"
            " registered_at REAL NOT"
            " NULL,"
            " PRIMARY KEY (schema_id,"
            " version))",
        ),
    ),
)


class SchemaNotFoundError(NotFoundError):
    """Schema not registered."""


@dataclass(frozen=True)
class SchemaVersion:
    schema_id: str
    version: int
    definition: str
    registered_at: float


@dataclass(frozen=True)
class NegotiationResult:
    schema_id: str
    agreed_version: int


class InteroperabilityEngine:
    """Versioned schemas with negotiation."""

    def __init__(
        self, db: Database, clock: Clock
    ) -> None:
        self._db = db
        self._clock = clock
        MigrationRunner(
            db,
            "interoperability",
            _MIGRATIONS,
        ).run(clock)

    def register_schema(
        self,
        *,
        schema_id: str,
        version: int,
        definition: str,
    ) -> SchemaVersion:
        require_non_empty_str(
            schema_id, "schema_id"
        )
        require_int_range(
            version, "version", 1, 10**6
        )
        require_non_empty_str(
            definition, "definition"
        )
        now = self._clock.now()
        with (
            self._db.transaction()
            as cursor
        ):
            cursor.execute(
                "INSERT INTO interop_schemas"
                " (schema_id, version,"
                "  definition,"
                "  registered_at)"
                " VALUES (?, ?, ?, ?)"
                " ON CONFLICT(schema_id,"
                " version) DO UPDATE SET"
                " definition ="
                " excluded.definition",
                (
                    schema_id,
                    version,
                    definition,
                    now,
                ),
            )
        return SchemaVersion(
            schema_id=schema_id,
            version=version,
            definition=definition,
            registered_at=now,
        )

    def get_schema(
        self,
        *,
        schema_id: str,
        version: int,
    ) -> SchemaVersion:
        require_non_empty_str(
            schema_id, "schema_id"
        )
        row = self._db.query_one(
            "SELECT * FROM interop_schemas"
            " WHERE schema_id = ?"
            " AND version = ?",
            (schema_id, version),
        )
        if row is None:
            raise SchemaNotFoundError(
                "unknown schema version:"
                f" {schema_id} v{version}"
            )
        return SchemaVersion(
            schema_id=str(
                row["schema_id"]
            ),
            version=int(row["version"]),
            definition=str(
                row["definition"]
            ),
            registered_at=float(
                row["registered_at"]
            ),
        )

    def list_versions(
        self, *, schema_id: str
    ) -> tuple[int, ...]:
        require_non_empty_str(
            schema_id, "schema_id"
        )
        rows = self._db.query_all(
            "SELECT version FROM"
            " interop_schemas"
            " WHERE schema_id = ?"
            " ORDER BY version",
            (schema_id,),
        )
        return tuple(
            int(r["version"])
            for r in rows
        )

    def negotiate(
        self,
        *,
        schema_id: str,
        client_versions: tuple[int, ...],
    ) -> NegotiationResult:
        require_non_empty_str(
            schema_id, "schema_id"
        )
        if not client_versions:
            raise UnsupportedVersionError(
                "client offered no"
                " versions"
            )
        ours = set(
            self.list_versions(
                schema_id=schema_id
            )
        )
        if not ours:
            raise SchemaNotFoundError(
                "unknown schema:"
                f" {schema_id}"
            )
        common = ours & set(
            client_versions
        )
        if not common:
            ours_sorted = sorted(ours)
            client_sorted = sorted(
                set(client_versions)
            )
            raise (
                UnsupportedVersionError(
                    "no mutual version:"
                    f" ours"
                    f" {ours_sorted} vs"
                    " client"
                    f" {client_sorted}"
                )
            )
        return NegotiationResult(
            schema_id=schema_id,
            agreed_version=max(common),
        )
