"""Checksummed, ordered, immutable schema migrations.

Re-running validates applied checksums and refuses to rewrite
history. Namespaces avoid version collisions between engines.
"""
from __future__ import annotations

import hashlib
from collections.abc import Sequence
from dataclasses import dataclass

from shared_engines.common.clocks import Clock
from shared_engines.common.errors import MigrationError
from shared_engines.common.validation import require_non_empty_str
from shared_engines.storage.database import Database


@dataclass(frozen=True)
class Migration:
    version: int
    name: str
    statements: tuple[str, ...]

    def __post_init__(self) -> None:
        if self.version <= 0:
            raise MigrationError("migration version must be positive")
        require_non_empty_str(self.name, "migration name", config=True)
        if not self.statements:
            raise MigrationError("migration must contain statements")

    @property
    def checksum(self) -> str:
        digest = hashlib.sha256()
        for statement in self.statements:
            digest.update(statement.strip().encode("utf-8"))
            digest.update(b"\x1e")
        return digest.hexdigest()


class MigrationRunner:
    def __init__(
        self,
        db: Database,
        namespace: str,
        migrations: Sequence[Migration],
    ) -> None:
        require_non_empty_str(namespace, "namespace", config=True)
        if not migrations:
            raise MigrationError("a migration set must not be empty")
        versions = [m.version for m in migrations]
        if versions != sorted(versions) or len(set(versions)) != len(
            versions
        ):
            raise MigrationError("versions must be unique and ascending")
        self._db = db
        self._namespace = namespace
        self._migrations = tuple(migrations)

    def run(self, clock: Clock) -> tuple[int, ...]:
        self._db.execute(
            "CREATE TABLE IF NOT EXISTS schema_migrations ("
            " namespace TEXT NOT NULL, version INTEGER NOT NULL,"
            " name TEXT NOT NULL, checksum TEXT NOT NULL,"
            " applied_at REAL NOT NULL,"
            " PRIMARY KEY (namespace, version))"
        )
        applied = {
            int(row["version"]): str(row["checksum"])
            for row in self._db.query_all(
                "SELECT version, checksum FROM schema_migrations"
                " WHERE namespace = ?",
                (self._namespace,),
            )
        }
        for migration in self._migrations:
            recorded = applied.get(migration.version)
            if recorded is not None:
                if recorded != migration.checksum:
                    raise MigrationError(
                        f"migration {self._namespace}."
                        f"v{migration.version} ({migration.name})"
                        " was modified after application"
                    )
                continue
            self._apply(migration, clock)
        return tuple(m.version for m in self._migrations)

    def _apply(self, migration: Migration, clock: Clock) -> None:
        with self._db.transaction() as cursor:
            for statement in migration.statements:
                cursor.execute(statement)
            cursor.execute(
                "INSERT INTO schema_migrations"
                " (namespace, version, name, checksum, applied_at)"
                " VALUES (?, ?, ?, ?, ?)",
                (self._namespace, migration.version, migration.name,
                 migration.checksum, clock.now()),
            )
