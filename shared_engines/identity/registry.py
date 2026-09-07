"""Durable identity registry: CRUD + lifecycle transitions.

Every transition runs inside one transaction, is validated
against the allowed transitions table, writes the outbox
event atomically with the state change, and leaves an audit
record through the tamper-evident chain.
"""
from __future__ import annotations

import sqlite3
from dataclasses import dataclass

from shared_engines.audit.chain import AuditTrail
from shared_engines.common.clocks import Clock
from shared_engines.common.errors import IntegrityError
from shared_engines.common.identifiers import new_id
from shared_engines.common.validation import require_non_empty_str
from shared_engines.events.contracts import EventCatalog
from shared_engines.events.outbox import Outbox
from shared_engines.identity.contracts import (
    Identity,
    IdentityKind,
    IdentityStatus,
    VALID_TRANSITIONS,
)
from shared_engines.identity.errors import (
    IdentityAlreadyExistsError,
    IdentityNotFoundError,
    InvalidTransitionError,
)
from shared_engines.storage.database import Database
from shared_engines.storage.migrations import Migration, MigrationRunner

EVENT_IDENTITY_REGISTERED = "identity.registered"
EVENT_IDENTITY_STATUS_CHANGED = "identity.status_changed"

IDENTITY_MIGRATIONS = (
    Migration(
        1,
        "identities",
        (
            "CREATE TABLE identities ("
            " zid TEXT PRIMARY KEY,"
            " kind TEXT NOT NULL,"
            " status TEXT NOT NULL,"
            " display_name TEXT NOT NULL,"
            " created_at REAL NOT NULL,"
            " updated_at REAL NOT NULL,"
            " contract_version INTEGER NOT NULL)",
            "CREATE INDEX identities_status ON identities (status)",
            "CREATE INDEX identities_kind ON identities (kind)",
        ),
    ),
)


@dataclass(frozen=True)
class RegistryPage:
    items: tuple[Identity, ...]
    offset: int
    limit: int
    total: int

    @property
    def has_more(self) -> bool:
        return self.offset + len(self.items) < self.total


class IdentityRegistry:
    """Durable store and lifecycle authority for identities."""

    def __init__(
        self,
        db: Database,
        clock: Clock,
        audit: AuditTrail,
        outbox: Outbox,
        catalog: EventCatalog,
    ) -> None:
        self._db = db
        self._clock = clock
        self._audit = audit
        self._outbox = outbox
        self._catalog = catalog
        MigrationRunner(db, "identity", IDENTITY_MIGRATIONS).run(clock)

    def create(
        self,
        *,
        kind: IdentityKind,
        display_name: str,
        actor: str,
    ) -> Identity:
        require_non_empty_str(display_name, "display_name")
        require_non_empty_str(actor, "actor")
        zid = f"ZID-{new_id()}"
        now = self._clock.now()
        try:
            with self._db.transaction() as cursor:
                cursor.execute(
                    "INSERT INTO identities"
                    " (zid, kind, status, display_name,"
                    "  created_at, updated_at, contract_version)"
                    " VALUES (?, ?, ?, ?, ?, ?, ?)",
                    (
                        zid,
                        kind.value,
                        IdentityStatus.REGISTERED.value,
                        display_name,
                        now,
                        now,
                        1,
                    ),
                )
                self._emit_transition(
                    cursor,
                    zid=zid,
                    from_status=None,
                    to_status=IdentityStatus.REGISTERED,
                    actor=actor,
                    reason="registration",
                )
        except sqlite3.IntegrityError as exc:
            raise IdentityAlreadyExistsError(
                f"zid collision: {zid}"
            ) from exc
        self._audit.append(
            event_type=EVENT_IDENTITY_REGISTERED,
            actor=actor,
            subject=zid,
            payload={
                "kind": kind.value,
                "display_name": display_name,
            },
        )
        created = self.get(zid)
        if created is None:
            raise IntegrityError("identity vanished after insert")
        return created

    def get(self, zid: str) -> Identity | None:
        row = self._db.query_one(
            "SELECT * FROM identities WHERE zid = ?", (zid,)
        )
        if row is None:
            return None
        return self._identity_from_row(row)

    def require(self, zid: str) -> Identity:
        identity = self.get(zid)
        if identity is None:
            raise IdentityNotFoundError(f"unknown zid: {zid}")
        return identity

    def transition(
        self,
        zid: str,
        to_status: IdentityStatus,
        *,
        actor: str,
        reason: str,
    ) -> Identity:
        require_non_empty_str(actor, "actor")
        require_non_empty_str(reason, "reason")
        with self._db.transaction() as cursor:
            row = cursor.execute(
                "SELECT * FROM identities WHERE zid = ?", (zid,)
            ).fetchone()
            if row is None:
                raise IdentityNotFoundError(f"unknown zid: {zid}")
            current = IdentityStatus(str(row["status"]))
            allowed = VALID_TRANSITIONS.get(current, frozenset())
            if to_status not in allowed:
                raise InvalidTransitionError(
                    f"{current.value} -> {to_status.value}"
                    " is not a valid transition"
                )
            now = self._clock.now()
            cursor.execute(
                "UPDATE identities SET status = ?, updated_at = ?"
                " WHERE zid = ?",
                (to_status.value, now, zid),
            )
            self._emit_transition(
                cursor,
                zid=zid,
                from_status=current,
                to_status=to_status,
                actor=actor,
                reason=reason,
            )
        self._audit.append(
            event_type=EVENT_IDENTITY_STATUS_CHANGED,
            actor=actor,
            subject=zid,
            payload={
                "from": current.value,
                "to": to_status.value,
                "reason": reason,
            },
        )
        return self.require(zid)

    def list_by_status(
        self,
        status: IdentityStatus,
        *,
        offset: int = 0,
        limit: int = 50,
    ) -> RegistryPage:
        total_row = self._db.query_one(
            "SELECT COUNT(*) AS n FROM identities WHERE status = ?",
            (status.value,),
        )
        total = int(total_row["n"]) if total_row is not None else 0
        rows = self._db.query_all(
            "SELECT * FROM identities WHERE status = ?"
            " ORDER BY created_at, zid LIMIT ? OFFSET ?",
            (status.value, limit, offset),
        )
        items = tuple(self._identity_from_row(row) for row in rows)
        return RegistryPage(
            items=items, offset=offset, limit=limit, total=total
        )

    def _emit_transition(
        self,
        cursor: sqlite3.Cursor,
        *,
        zid: str,
        from_status: IdentityStatus | None,
        to_status: IdentityStatus,
        actor: str,
        reason: str,
    ) -> None:
        event_type = (
            EVENT_IDENTITY_REGISTERED
            if from_status is None
            else EVENT_IDENTITY_STATUS_CHANGED
        )
        payload: dict[str, object] = {
            "zid": zid,
            "to": to_status.value,
            "actor": actor,
            "reason": reason,
        }
        if from_status is not None:
            payload["from"] = from_status.value
        event = self._catalog.build(
            event_type,
            aggregate_id=zid,
            payload=payload,
            clock=self._clock,
        )
        self._outbox.enqueue_in_transaction(cursor, event)

    @staticmethod
    def _identity_from_row(row: sqlite3.Row) -> Identity:
        return Identity(
            zid=str(row["zid"]),
            kind=IdentityKind(str(row["kind"])),
            status=IdentityStatus(str(row["status"])),
            display_name=str(row["display_name"]),
            created_at=float(row["created_at"]),
            updated_at=float(row["updated_at"]),
            contract_version=int(row["contract_version"]),
        )
