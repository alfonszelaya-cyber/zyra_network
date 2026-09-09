"""System loader: manifest-governed component
loading.

The GOVERNANCE layer above execution (foundation
ModuleLoader/ComponentLoader do the actual import;
LifecycleManager runs states). This engine decides
WHAT MAY LOAD and records it durably:

    manifest declared (component, version,
                       compatible contract range)
          |
          v
    load_component(): policy check
    (contract version within range, not loaded)
          |
          v
    durable loaded-registry + outbox event

Policy is compatibility-based and explicit: an
out-of-range component can never load, and a
component cannot load twice. This is the
anti-arbitrary-loading guard the audit demanded.
"""
from __future__ import annotations

import hashlib
import sqlite3
from dataclasses import dataclass

from shared_engines.common.clocks import Clock
from shared_engines.common.identifiers import (
    new_id,
)
from shared_engines.common.serialization import (
    canonical_json_dumps,
)
from shared_engines.common.validation import (
    require_int_range,
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
from shared_engines.system_loader.errors import (
    ComponentAlreadyLoadedError,
    IncompatibleVersionError,
    ManifestNotRegisteredError,
    UnknownLoadedComponentError,
)

EVENT_LOADED = "system.component.loaded"
EVENT_UNLOADED = (
    "system.component.unloaded"
)

_MIGRATIONS = (
    Migration(
        1,
        "system_loader",
        (
            "CREATE TABLE"
            " system_manifests ("
            " component_id TEXT NOT NULL,"
            " version INTEGER NOT NULL,"
            " min_contract INTEGER NOT"
            " NULL,"
            " max_contract INTEGER NOT"
            " NULL,"
            " registered_at REAL NOT"
            " NULL,"
            " PRIMARY KEY (component_id,"
            " version))",
            "CREATE TABLE system_loaded ("
            " component_id TEXT PRIMARY"
            " KEY,"
            " version INTEGER NOT NULL,"
            " loaded_at REAL NOT NULL)",
        ),
    ),
)


@dataclass(frozen=True)
class ManifestRecord:
    component_id: str
    version: int
    min_contract: int
    max_contract: int
    registered_at: float


@dataclass(frozen=True)
class LoadedRecord:
    component_id: str
    version: int
    loaded_at: float


class SystemLoaderEngine:
    """Manifest policy over durable load
    registry."""

    def __init__(
        self,
        db: Database,
        clock: Clock,
        *,
        outbox: Outbox,
        network_contract_version: int = 1,
    ) -> None:
        require_int_range(
            network_contract_version,
            "network_contract_version",
            1,
            10**6,
            config=True,
        )
        self._db = db
        self._clock = clock
        self._outbox = outbox
        self._contract = (
            network_contract_version
        )
        MigrationRunner(
            db,
            "system_loader",
            _MIGRATIONS,
        ).run(clock)

    def _emit(
        self,
        cursor: sqlite3.Cursor,
        *,
        event_type: str,
        aggregate: str,
        payload: dict[str, object],
    ) -> None:
        uid = hashlib.sha256(
            canonical_json_dumps(
                {
                    "t": event_type,
                    "a": aggregate,
                    "u": new_id(),
                }
            ).encode("utf-8")
        ).hexdigest()[:32]
        fp = hashlib.sha256(
            canonical_json_dumps(
                {
                    "id": uid,
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
                uid,
                event_type,
                aggregate,
                self._clock.now(),
                canonical_json_dumps(
                    payload
                ),
                fp,
            ),
        )

    def register_manifest(
        self,
        *,
        component_id: str,
        version: int,
        min_contract: int,
        max_contract: int,
    ) -> ManifestRecord:
        require_non_empty_str(
            component_id,
            "component_id",
        )
        require_int_range(
            version, "version", 1, 10**6
        )
        require_int_range(
            min_contract,
            "min_contract",
            1,
            10**6,
        )
        require_int_range(
            max_contract,
            "max_contract",
            1,
            10**6,
        )
        if min_contract > max_contract:
            raise ValueError(
                "min_contract exceeds"
                " max_contract"
            )
        now = self._clock.now()
        with (
            self._db.transaction()
            as cursor
        ):
            cursor.execute(
                "INSERT INTO"
                " system_manifests"
                " (component_id, version,"
                "  min_contract,"
                "  max_contract,"
                "  registered_at)"
                " VALUES (?, ?, ?, ?, ?)"
                " ON CONFLICT("
                " component_id, version)"
                " DO UPDATE SET"
                " min_contract ="
                " excluded.min_contract,"
                " max_contract ="
                " excluded.max_contract",
                (
                    component_id,
                    version,
                    min_contract,
                    max_contract,
                    now,
                ),
            )
        return ManifestRecord(
            component_id=component_id,
            version=version,
            min_contract=min_contract,
            max_contract=max_contract,
            registered_at=now,
        )

    def _pick_manifest(
        self,
        component_id: str,
        version: int | None,
    ) -> ManifestRecord:
        if version is not None:
            row = self._db.query_one(
                "SELECT * FROM"
                " system_manifests"
                " WHERE component_id = ?"
                " AND version = ?",
                (component_id, version),
            )
        else:
            row = self._db.query_one(
                "SELECT * FROM"
                " system_manifests"
                " WHERE component_id = ?"
                " ORDER BY version DESC"
                " LIMIT 1",
                (component_id,),
            )
        if row is None:
            raise (
                ManifestNotRegisteredError(
                    "no manifest for"
                    f" '{component_id}'"
                )
            )
        return ManifestRecord(
            component_id=str(
                row["component_id"]
            ),
            version=int(
                row["version"]
            ),
            min_contract=int(
                row["min_contract"]
            ),
            max_contract=int(
                row["max_contract"]
            ),
            registered_at=float(
                row["registered_at"]
            ),
        )

    def load_component(
        self,
        *,
        component_id: str,
        version: int | None = None,
    ) -> LoadedRecord:
        require_non_empty_str(
            component_id,
            "component_id",
        )
        already = self._db.query_one(
            "SELECT 1 FROM"
            " system_loaded WHERE"
            " component_id = ?",
            (component_id,),
        )
        if already is not None:
            raise (
                ComponentAlreadyLoadedError(
                    "already loaded:"
                    f" {component_id}"
                )
            )
        manifest = self._pick_manifest(
            component_id, version
        )
        if not (
            manifest.min_contract
            <= self._contract
            <= manifest.max_contract
        ):
            raise (
                IncompatibleVersionError(
                    f"'{component_id}'"
                    f" v{manifest.version}"
                    " needs contract"
                    " ["
                    f"{manifest.min_contract}"
                    ","
                    f"{manifest.max_contract}"
                    "] but network is"
                    f" {self._contract}"
                )
            )
        now = self._clock.now()
        with (
            self._db.transaction()
            as cursor
        ):
            cursor.execute(
                "INSERT INTO"
                " system_loaded"
                " (component_id, version,"
                "  loaded_at)"
                " VALUES (?, ?, ?)",
                (
                    component_id,
                    manifest.version,
                    now,
                ),
            )
            self._emit(
                cursor,
                event_type=EVENT_LOADED,
                aggregate=component_id,
                payload={
                    "version": (
                        manifest.version
                    )
                },
            )
        return LoadedRecord(
            component_id=component_id,
            version=manifest.version,
            loaded_at=now,
        )

    def unload_component(
        self, *, component_id: str
    ) -> LoadedRecord:
        require_non_empty_str(
            component_id,
            "component_id",
        )
        row = self._db.query_one(
            "SELECT * FROM system_loaded"
            " WHERE component_id = ?",
            (component_id,),
        )
        if row is None:
            raise (
                UnknownLoadedComponentError(
                    "not loaded:"
                    f" {component_id}"
                )
            )
        record = LoadedRecord(
            component_id=str(
                row["component_id"]
            ),
            version=int(row["version"]),
            loaded_at=float(
                row["loaded_at"]
            ),
        )
        with (
            self._db.transaction()
            as cursor
        ):
            cursor.execute(
                "DELETE FROM"
                " system_loaded WHERE"
                " component_id = ?",
                (component_id,),
            )
            self._emit(
                cursor,
                event_type=(
                    EVENT_UNLOADED
                ),
                aggregate=component_id,
                payload={
                    "version": (
                        record.version
                    )
                },
            )
        return record

    def loaded_components(
        self,
    ) -> tuple[LoadedRecord, ...]:
        rows = self._db.query_all(
            "SELECT * FROM system_loaded"
            " ORDER BY component_id"
        )
        return tuple(
            LoadedRecord(
                component_id=str(
                    r["component_id"]
                ),
                version=int(
                    r["version"]
                ),
                loaded_at=float(
                    r["loaded_at"]
                ),
            )
            for r in rows
        )
