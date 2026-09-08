"""Accredited certifier registry: WHO may certify
WHAT. An issuer is a Network identity (ZID) formally
accredited for explicit certification scopes;
issuing outside accredited scopes is impossible by
construction."""
from __future__ import annotations

from shared_engines.common.clocks import Clock
from shared_engines.common.validation import (
    require_non_empty_str,
)
from shared_engines.certification.contracts import (
    IssuerRecord,
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
        "certification_issuers",
        (
            "CREATE TABLE"
            " certification_issuers ("
            " issuer_id TEXT PRIMARY KEY,"
            " display_name TEXT NOT NULL,"
            " scopes TEXT NOT NULL,"
            " registered_at REAL NOT NULL,"
            " active INTEGER NOT NULL"
            " DEFAULT 1)",
        ),
    ),
)


class IssuerRegistry:
    """Durable accreditation of certifiers."""

    def __init__(
        self,
        db: Database,
        clock: Clock,
    ) -> None:
        self._db = db
        self._clock = clock
        MigrationRunner(
            db,
            "certification.issuers",
            _MIGRATIONS,
        ).run(clock)

    def register_issuer(
        self,
        *,
        issuer_id: str,
        display_name: str,
        scopes: tuple[str, ...],
    ) -> IssuerRecord:
        require_non_empty_str(
            issuer_id, "issuer_id"
        )
        require_non_empty_str(
            display_name,
            "display_name",
        )
        clean: list[str] = []
        for scope in scopes:
            require_non_empty_str(
                scope, "scope"
            )
            if scope not in clean:
                clean.append(scope)
        if not clean:
            raise ValueError(
                "at least one scope"
                " required"
            )
        now = self._clock.now()
        with (
            self._db.transaction()
            as cursor
        ):
            cursor.execute(
                "INSERT INTO"
                " certification_issuers"
                " (issuer_id,"
                " display_name, scopes,"
                " registered_at, active)"
                " VALUES (?, ?, ?, ?, 1)"
                " ON CONFLICT(issuer_id)"
                " DO UPDATE SET"
                " display_name ="
                " excluded.display_name,"
                " scopes ="
                " excluded.scopes,"
                " active = 1",
                (
                    issuer_id,
                    display_name,
                    ",".join(clean),
                    now,
                ),
            )
        return IssuerRecord(
            issuer_id=issuer_id,
            display_name=(
                display_name
            ),
            scopes=tuple(clean),
            registered_at=now,
            active=True,
        )

    def deactivate_issuer(
        self, issuer_id: str
    ) -> None:
        require_non_empty_str(
            issuer_id, "issuer_id"
        )
        with (
            self._db.transaction()
            as cursor
        ):
            cursor.execute(
                "UPDATE"
                " certification_issuers"
                " SET active = 0"
                " WHERE issuer_id = ?",
                (issuer_id,),
            )

    def get_issuer(
        self, issuer_id: str
    ) -> IssuerRecord | None:
        row = self._db.query_one(
            "SELECT * FROM"
            " certification_issuers"
            " WHERE issuer_id = ?",
            (issuer_id,),
        )
        if row is None:
            return None
        return IssuerRecord(
            issuer_id=str(
                row["issuer_id"]
            ),
            display_name=str(
                row["display_name"]
            ),
            scopes=tuple(
                s
                for s in str(
                    row["scopes"]
                ).split(",")
                if s
            ),
            registered_at=float(
                row["registered_at"]
            ),
            active=bool(
                int(row["active"])
            ),
        )

    def has_scope(
        self,
        *,
        issuer_id: str,
        scope: str,
    ) -> bool:
        issuer = self.get_issuer(
            issuer_id
        )
        if issuer is None:
            return False
        return (
            issuer.active
            and scope
            in issuer.scopes
        )
