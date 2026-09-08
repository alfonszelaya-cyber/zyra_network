"""Portable identity profile: one registration,
recognized across every authorized app.

Federation layer of the Network:

    App registration (NEXO, Subastas, ...)
          |
          v
    ZID (one identity for the whole Network)
          |
          v
    ProfileRegistry (fields + verification level
                     + source evidence)
          |
          v
    CrossAppAccess (authorized app queries a ZID;
    only permitted fields are returned; every access
    is audited as network.profile.accessed)

Guarantees:

- Profile state lives in its OWN tables (never
  touches identity/ storage).
- Every field carries a verification level:
  SELF_DECLARED or VERIFIED (evidence-backed).
- Apps register with scopes; queries return only
  the intersection of scopes and filled fields.
- Every cross-app access is audited and emits
  network.profile.accessed to the Outbox.
- Transactions never nest: the audit entry is
  written first (own transaction), then the
  outbox event in a separate short transaction.
"""
from __future__ import annotations

import hashlib
import sqlite3
from dataclasses import dataclass

from shared_engines.audit.chain import AuditTrail
from shared_engines.common.clocks import Clock
from shared_engines.common.serialization import (
    canonical_json_dumps,
)
from shared_engines.common.validation import (
    require_non_empty_str,
)
from shared_engines.events.outbox import Outbox
from shared_engines.storage.database import (
    Database,
)
from shared_engines.storage.migrations import (
    Migration,
    MigrationRunner,
)

EVENT_PROFILE_ACCESSED = (
    "network.profile.accessed"
)
EVENT_PROFILE_UPDATED = (
    "network.profile.updated"
)

LEVEL_SELF = "SELF_DECLARED"
LEVEL_VERIFIED = "VERIFIED"

ALL_FIELDS = (
    "display_name",
    "contact",
    "national_id",
    "birth_date",
    "address",
)

_MIGRATIONS = (
    Migration(
        1,
        "network_portable_profile",
        (
            "CREATE TABLE app_registry ("
            " app_id TEXT PRIMARY KEY,"
            " display_name TEXT NOT NULL,"
            " scopes TEXT NOT NULL,"
            " registered_at REAL NOT NULL)",
            "CREATE TABLE profile_fields ("
            " zid TEXT NOT NULL,"
            " field TEXT NOT NULL,"
            " value TEXT NOT NULL,"
            " level TEXT NOT NULL,"
            " source_hash TEXT NOT NULL,"
            " updated_at REAL NOT NULL,"
            " PRIMARY KEY (zid, field))",
        ),
    ),
)


@dataclass(frozen=True)
class AppRegistration:
    app_id: str
    display_name: str
    scopes: tuple[str, ...]


@dataclass(frozen=True)
class ProfileView:
    """What an app may see for one ZID."""

    zid: str
    fields: dict[str, str]
    levels: dict[str, str]


def _source_hash(
    zid: str, field: str, value: str
) -> str:
    src = canonical_json_dumps(
        {
            "zid": zid,
            "field": field,
            "value": value,
        }
    )
    return hashlib.sha256(
        src.encode("utf-8")
    ).hexdigest()


class ProfileRegistry:
    """Trust profile bound to a Network ZID."""

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
            db,
            "network.portable_profile",
            _MIGRATIONS,
        ).run(clock)

    def register_app(
        self,
        *,
        app_id: str,
        display_name: str,
        scopes: tuple[str, ...],
    ) -> AppRegistration:
        require_non_empty_str(
            app_id, "app_id"
        )
        require_non_empty_str(
            display_name, "display_name"
        )
        clean: list[str] = []
        for scope in scopes:
            require_non_empty_str(
                scope, "scope"
            )
            if scope not in ALL_FIELDS:
                raise ValueError(
                    f"unknown scope:"
                    f" {scope}"
                )
            if scope not in clean:
                clean.append(scope)
        if not clean:
            raise ValueError(
                "at least one scope"
                " required"
            )
        with self._db.transaction() as cursor:
            cursor.execute(
                "INSERT INTO app_registry"
                " (app_id, display_name,"
                " scopes, registered_at)"
                " VALUES (?, ?, ?, ?)"
                " ON CONFLICT(app_id) DO"
                " UPDATE SET display_name ="
                " excluded.display_name,"
                " scopes = excluded.scopes",
                (
                    app_id,
                    display_name,
                    ",".join(clean),
                    self._clock.now(),
                ),
            )
        return AppRegistration(
            app_id=app_id,
            display_name=display_name,
            scopes=tuple(clean),
        )

    def set_field(
        self,
        *,
        zid: str,
        field: str,
        value: str,
        verified: bool = False,
    ) -> None:
        require_non_empty_str(
            zid, "zid"
        )
        require_non_empty_str(
            field, "field"
        )
        if field not in ALL_FIELDS:
            raise ValueError(
                f"unknown field: {field}"
            )
        require_non_empty_str(
            value, "value"
        )
        level = (
            LEVEL_VERIFIED
            if verified
            else LEVEL_SELF
        )
        src = _source_hash(
            zid, field, value
        )
        with self._db.transaction() as cursor:
            cursor.execute(
                "INSERT INTO profile_fields"
                " (zid, field, value, level,"
                "  source_hash, updated_at)"
                " VALUES (?, ?, ?, ?, ?, ?)"
                " ON CONFLICT(zid, field)"
                " DO UPDATE SET value ="
                " excluded.value, level ="
                " excluded.level,"
                " source_hash ="
                " excluded.source_hash,"
                " updated_at ="
                " excluded.updated_at",
                (
                    zid,
                    field,
                    value,
                    level,
                    src,
                    self._clock.now(),
                ),
            )
            self._emit(
                cursor,
                event_type=(
                    EVENT_PROFILE_UPDATED
                ),
                aggregate=zid,
                payload={
                    "field": field,
                    "level": level,
                },
            )

    def _emit(
        self,
        cursor: sqlite3.Cursor,
        *,
        event_type: str,
        aggregate: str,
        payload: dict[str, object],
    ) -> None:
        """Durably enqueue an outbox event
        inside the caller's transaction."""
        event_id_src = canonical_json_dumps(
            {
                "t": event_type,
                "a": aggregate,
                "p": payload,
                "ts": self._clock.now(),
            }
        )
        event_id = hashlib.sha256(
            event_id_src.encode("utf-8")
        ).hexdigest()[:32]
        fp = hashlib.sha256(
            canonical_json_dumps(
                {
                    "id": event_id,
                    "ty": event_type,
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
                event_type,
                aggregate,
                self._clock.now(),
                canonical_json_dumps(
                    payload
                ),
                fp,
            ),
        )

    def app_scopes(
        self, app_id: str
    ) -> tuple[str, ...] | None:
        row = self._db.query_one(
            "SELECT scopes FROM"
            " app_registry"
            " WHERE app_id = ?",
            (app_id,),
        )
        if row is None:
            return None
        return tuple(
            s
            for s in str(
                row["scopes"]
            ).split(",")
            if s
        )

    def view_for_app(
        self,
        *,
        app_id: str,
        zid: str,
    ) -> ProfileView:
        """Authorized cross-app read.

        Only fields in the app's scopes AND
        present in the profile are returned.
        Every call is audited and emits
        network.profile.accessed.

        Transaction discipline: the audit
        append owns its transaction, so it runs
        BEFORE the short outbox transaction
        (no nesting).
        """
        require_non_empty_str(
            app_id, "app_id"
        )
        require_non_empty_str(
            zid, "zid"
        )
        scopes = self.app_scopes(app_id)
        if scopes is None:
            raise PermissionError(
                "app not registered:"
                f" {app_id}"
            )
        fields: dict[str, str] = {}
        levels: dict[str, str] = {}
        rows = self._db.query_all(
            "SELECT field, value, level"
            " FROM profile_fields"
            " WHERE zid = ?",
            (zid,),
        )
        for row in rows:
            field = str(row["field"])
            if field not in scopes:
                continue
            fields[field] = str(
                row["value"]
            )
            levels[field] = str(
                row["level"]
            )
        accessed_fields = sorted(
            fields.keys()
        )
        self._audit.append(
            event_type=(
                EVENT_PROFILE_ACCESSED
            ),
            actor=app_id,
            subject=zid,
            payload={
                "fields": accessed_fields,
            },
        )
        with self._db.transaction() as cursor:
            self._emit(
                cursor,
                event_type=(
                    EVENT_PROFILE_ACCESSED
                ),
                aggregate=zid,
                payload={
                    "app": app_id,
                    "fields": (
                        accessed_fields
                    ),
                },
            )
        return ProfileView(
            zid=zid,
            fields=fields,
            levels=levels,
        )
