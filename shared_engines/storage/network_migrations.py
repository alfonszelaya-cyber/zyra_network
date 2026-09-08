"""Central migration registry: one entry migrates ALL engines."""
from __future__ import annotations

from dataclasses import dataclass

from shared_engines.common.clocks import Clock
from shared_engines.storage.database import Database
from shared_engines.storage.migrations import (
    Migration,
    MigrationRunner,
)


@dataclass(frozen=True)
class NamespaceResult:
    namespace: str
    applied_now: tuple[int, ...]
    versions: tuple[int, ...]


@dataclass(frozen=True)
class NetworkMigrationReport:
    results: tuple[NamespaceResult, ...]

    @property
    def total_applied_now(self) -> int:
        return sum(len(r.applied_now) for r in self.results)


class NetworkMigrationRunner:
    """Runs every engine's migrations in deterministic order."""

    def __init__(self, db: Database, clock: Clock) -> None:
        self._db = db
        self._clock = clock

    def _registry(
        self,
    ) -> tuple[tuple[str, tuple[Migration, ...]], ...]:
        from shared_engines.audit.chain import MIGRATIONS as AUDIT
        from shared_engines.currency.engine import (
            CONVERSIONS_MIGRATIONS,
        )
        from shared_engines.currency.store import (
            RATES_MIGRATIONS,
        )
        from shared_engines.events.inbox import (
            MIGRATIONS as INBOX,
        )
        from shared_engines.events.outbox import (
            MIGRATIONS as OUTBOX,
        )
        from shared_engines.hardening.api_keys import (
            API_KEYS_MIGRATIONS,
        )
        from shared_engines.hardening.bruteforce import (
            BRUTE_FORCE_MIGRATIONS,
        )
        from shared_engines.hardening.ratelimit import (
            RATE_LIMIT_MIGRATIONS,
        )
        from shared_engines.identity.registry import (
            IDENTITY_MIGRATIONS,
        )
        from shared_engines.tokenization.ledger import (
            TOKEN_MIGRATIONS,
        )
        from shared_engines.verification.attestations import (
            ATTESTATION_MIGRATIONS,
        )
        from shared_engines.verification.credentials import (
            CREDENTIALS_MIGRATIONS,
        )
        from shared_engines.verification.media import (
            MEDIA_MIGRATIONS,
        )
        from shared_engines.verification.provenance import (
            PROVENANCE_MIGRATIONS,
        )

        return (
            ("audit", AUDIT),
            ("events.outbox", OUTBOX),
            ("events.inbox", INBOX),
            ("identity", IDENTITY_MIGRATIONS),
            ("verification.media", MEDIA_MIGRATIONS),
            ("verification.provenance", PROVENANCE_MIGRATIONS),
            ("verification.credentials", CREDENTIALS_MIGRATIONS),
            ("verification.attestations", ATTESTATION_MIGRATIONS),
            ("currency.rates", RATES_MIGRATIONS),
            ("currency.conversions", CONVERSIONS_MIGRATIONS),
            ("tokenization", TOKEN_MIGRATIONS),
            ("hardening.keys", API_KEYS_MIGRATIONS),
            ("hardening.ratelimit", RATE_LIMIT_MIGRATIONS),
            ("hardening.bruteforce", BRUTE_FORCE_MIGRATIONS),
        )

    def run_all(self) -> NetworkMigrationReport:
        self._db.execute(
            "CREATE TABLE IF NOT EXISTS schema_migrations ("
            " namespace TEXT NOT NULL,"
            " version INTEGER NOT NULL,"
            " name TEXT NOT NULL,"
            " checksum TEXT NOT NULL,"
            " applied_at REAL NOT NULL,"
            " PRIMARY KEY (namespace, version))"
        )
        results: list[NamespaceResult] = []
        for namespace, migrations in self._registry():
            before = self._known_versions(namespace)
            runner = MigrationRunner(
                self._db, namespace, migrations
            )
            runner.run(self._clock)
            after = self._known_versions(namespace)
            applied_now = tuple(
                v for v in after if v not in before
            )
            results.append(
                NamespaceResult(
                    namespace=namespace,
                    applied_now=applied_now,
                    versions=after,
                )
            )
        return NetworkMigrationReport(results=tuple(results))

    def _known_versions(self, namespace: str) -> tuple[int, ...]:
        rows = self._db.query_all(
            "SELECT version FROM schema_migrations"
            " WHERE namespace = ? ORDER BY version",
            (namespace,),
        )
        return tuple(int(row["version"]) for row in rows)
