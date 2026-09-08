"""Search engine: the transversal query layer.

Composes EXISTING tables as sources - never
duplicating engines or creating parallel indexes:

    identity    -> identities (display_name)
    credential  -> credentials (title, not revoked)
    document    -> sealed_documents (title)
    certificate -> certificates (title, not revoked)
    history     -> life_history_entries (payload)

Guarantees:

- Authorized: only apps registered via
  ProfileRegistry (app_registry) may search.
- Auditable: every query is written to the
  durable search log, appended to the audit
  chain and emitted as network.search.performed
  with a unique event id (repeated queries are
  separate events, never deduplicated away).
- Ranked: exact title match (3) > prefix (2) >
  substring (1); stable tiebreak by title.
- Paginated with the existing common Page.
- Case-insensitive matching via lower() +
  instr(); no LIKE escaping issues.
- Missing source tables are skipped, so the
  engine works on partial deployments.

Transactions never nest: the log entry and
outbox event share one short transaction; the
audit append runs afterwards on its own.
"""
from __future__ import annotations

import hashlib
import sqlite3

from shared_engines.audit.chain import AuditTrail
from shared_engines.common.clocks import Clock
from shared_engines.common.identifiers import (
    new_id,
)
from shared_engines.common.pagination import Page
from shared_engines.common.serialization import (
    canonical_json_dumps,
)
from shared_engines.common.validation import (
    require_int_range,
    require_non_empty_str,
)
from shared_engines.events.outbox import Outbox
from shared_engines.search.contracts import (
    SearchHit,
)
from shared_engines.search.errors import (
    SearchNotAuthorizedError,
    UnknownSourceError,
)
from shared_engines.storage.database import (
    Database,
)
from shared_engines.storage.migrations import (
    Migration,
    MigrationRunner,
)

EVENT_SEARCH_PERFORMED = (
    "network.search.performed"
)

SOURCE_IDENTITY = "identity"
SOURCE_CREDENTIAL = "credential"
SOURCE_DOCUMENT = "document"
SOURCE_CERTIFICATE = "certificate"
SOURCE_HISTORY = "history"

ALL_SOURCES: tuple[str, ...] = (
    SOURCE_IDENTITY,
    SOURCE_CREDENTIAL,
    SOURCE_DOCUMENT,
    SOURCE_CERTIFICATE,
    SOURCE_HISTORY,
)

_MIGRATIONS = (
    Migration(
        1,
        "search_log",
        (
            "CREATE TABLE search_log ("
            " search_id INTEGER PRIMARY KEY"
            " AUTOINCREMENT,"
            " app_id TEXT NOT NULL,"
            " query TEXT NOT NULL,"
            " sources TEXT NOT NULL,"
            " result_count INTEGER NOT NULL,"
            " performed_at REAL NOT NULL)",
        ),
    ),
)

_SOURCE_QUERIES: dict[str, str] = {
    SOURCE_IDENTITY: (
        "SELECT zid AS ref_id,"
        " display_name AS title,"
        " display_name AS snippet"
        " FROM identities"
        " WHERE instr(lower(display_name),"
        " ?) > 0 LIMIT 500"
    ),
    SOURCE_CREDENTIAL: (
        "SELECT credential_id AS ref_id,"
        " title AS title,"
        " detail AS snippet"
        " FROM credentials"
        " WHERE revoked = 0"
        " AND instr(lower(title), ?) > 0"
        " LIMIT 500"
    ),
    SOURCE_DOCUMENT: (
        "SELECT document_id AS ref_id,"
        " title AS title,"
        " title AS snippet"
        " FROM sealed_documents"
        " WHERE instr(lower(title), ?)"
        " > 0 LIMIT 500"
    ),
    SOURCE_CERTIFICATE: (
        "SELECT certificate_id AS ref_id,"
        " title AS title,"
        " scope AS snippet"
        " FROM certificates"
        " WHERE revoked = 0"
        " AND instr(lower(title), ?) > 0"
        " LIMIT 500"
    ),
    SOURCE_HISTORY: (
        "SELECT zid || '#' || entry_seq"
        " AS ref_id,"
        " entry_type AS title,"
        " substr(payload, 1, 120)"
        " AS snippet"
        " FROM life_history_entries"
        " WHERE instr("
        " lower(payload), ?) > 0"
        " LIMIT 500"
    ),
}

_SOURCE_TABLES: dict[str, str] = {
    SOURCE_IDENTITY: "identities",
    SOURCE_CREDENTIAL: "credentials",
    SOURCE_DOCUMENT: "sealed_documents",
    SOURCE_CERTIFICATE: "certificates",
    SOURCE_HISTORY: (
        "life_history_entries"
    ),
}


class SearchEngine:
    """Authorized, audited, ranked global
    search over existing tables."""

    def __init__(
        self,
        db: Database,
        clock: Clock,
        *,
        audit: AuditTrail,
        outbox: Outbox,
    ) -> None:
        self._db = db
        self._clock = clock
        self._audit = audit
        self._outbox = outbox
        MigrationRunner(
            db, "search", _MIGRATIONS
        ).run(clock)

    def _require_app(
        self, app_id: str
    ) -> None:
        row = self._db.query_one(
            "SELECT 1 FROM app_registry"
            " WHERE app_id = ?",
            (app_id,),
        )
        if row is None:
            raise (
                SearchNotAuthorizedError(
                    "app not registered:"
                    f" {app_id}"
                )
            )

    def _table_exists(
        self, table: str
    ) -> bool:
        row = self._db.query_one(
            "SELECT 1 FROM sqlite_master"
            " WHERE type = 'table'"
            " AND name = ?",
            (table,),
        )
        return row is not None

    def _score(
        self, title: str, q: str
    ) -> int:
        t = title.lower()
        if t == q:
            return 3
        if t.startswith(q):
            return 2
        return 1

    def search(
        self,
        *,
        app_id: str,
        query: str,
        sources: tuple[str, ...] | None = None,
        offset: int = 0,
        limit: int = 20,
    ) -> Page[SearchHit]:
        """Global authorized search."""
        require_int_range(
            offset, "offset", 0, 10**12
        )
        require_int_range(
            limit, "limit", 1, 100
        )
        self._require_app(app_id)
        require_non_empty_str(
            query, "query"
        )
        q = query.strip().lower()
        chosen: tuple[str, ...]
        if sources is None:
            chosen = ALL_SOURCES
        else:
            for s in sources:
                if s not in ALL_SOURCES:
                    raise (
                        UnknownSourceError(
                            "unknown"
                            " source:"
                            f" {s}"
                        )
                    )
            chosen = sources
        hits: list[SearchHit] = []
        for source in chosen:
            table = _SOURCE_TABLES[
                source
            ]
            if not self._table_exists(
                table
            ):
                continue
            rows = self._db.query_all(
                _SOURCE_QUERIES[source],
                (q,),
            )
            for row in rows:
                title = str(
                    row["title"]
                )
                hits.append(
                    SearchHit(
                        source=source,
                        ref_id=str(
                            row["ref_id"]
                        ),
                        title=title,
                        snippet=str(
                            row["snippet"]
                        ),
                        score=self._score(
                            title, q
                        ),
                    )
                )
        hits.sort(
            key=lambda h: (
                -h.score,
                h.title,
                h.source,
                h.ref_id,
            )
        )
        total = len(hits)
        end = offset + limit
        window = hits[offset:end]
        with self._db.transaction() as cursor:
            cursor.execute(
                "INSERT INTO search_log"
                " (app_id, query, sources,"
                "  result_count,"
                "  performed_at)"
                " VALUES (?, ?, ?, ?, ?)",
                (
                    app_id,
                    q,
                    ",".join(chosen),
                    total,
                    self._clock.now(),
                ),
            )
            self._emit(
                cursor,
                app_id=app_id,
                q=q,
                total=total,
            )
        self._audit.append(
            event_type=(
                EVENT_SEARCH_PERFORMED
            ),
            actor=app_id,
            subject=q,
            payload={"results": total},
        )
        return Page(
            items=tuple(window),
            offset=offset,
            limit=limit,
            total=total,
        )

    def _emit(
        self,
        cursor: sqlite3.Cursor,
        *,
        app_id: str,
        q: str,
        total: int,
    ) -> None:
        """Unique event per execution:
        new_id() makes repeated identical
        queries distinct events."""
        event_id = hashlib.sha256(
            canonical_json_dumps(
                {
                    "a": app_id,
                    "q": q,
                    "ts": self._clock.now(),
                    "u": new_id(),
                }
            ).encode("utf-8")
        ).hexdigest()[:32]
        fp = hashlib.sha256(
            canonical_json_dumps(
                {
                    "id": event_id,
                    "ty": (
                        EVENT_SEARCH_PERFORMED
                    ),
                }
            ).encode("utf-8")
        ).hexdigest()
        cursor.execute(
            "INSERT INTO events_outbox"
            " (event_id, event_type,"
            " aggregate_id, schema_version,"
            " envelope_version, created_at,"
            " payload, fingerprint,"
            " published_at)"
            " VALUES (?, ?, ?, 1, 1, ?, ?,"
            " ?, NULL)",
            (
                event_id,
                EVENT_SEARCH_PERFORMED,
                app_id,
                self._clock.now(),
                canonical_json_dumps(
                    {
                        "query": q,
                        "results": total,
                    }
                ),
                fp,
            ),
        )

    def search_log_count(self) -> int:
        row = self._db.query_one(
            "SELECT COUNT(*) AS n FROM"
            " search_log"
        )
        return (
            int(row["n"])
            if row is not None
            else 0
        )
