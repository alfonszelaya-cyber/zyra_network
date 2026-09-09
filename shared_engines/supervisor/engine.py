"""Supervisor engine: component lifecycle with a
restart budget.

States: REGISTERED -> RUNNING <-> FAILED, with
QUARANTINED as terminal when the restart budget is
exhausted (a component that keeps dying is stopped
from thrashing the Network). Every failure and
restart is audited via the existing AuditTrail.
"""
from __future__ import annotations

from dataclasses import dataclass

from shared_engines.audit.chain import AuditTrail
from shared_engines.common.clocks import Clock
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
from shared_engines.supervisor.errors import (
    QuarantinedError,
    UnknownComponentError,
)

STATE_REGISTERED = "REGISTERED"
STATE_RUNNING = "RUNNING"
STATE_FAILED = "FAILED"
STATE_QUARANTINED = "QUARANTINED"

EVENT_SUPERVISOR_RESTART = (
    "supervisor.component.restarted"
)
EVENT_SUPERVISOR_FAILED = (
    "supervisor.component.failed"
)

_MIGRATIONS = (
    Migration(
        1,
        "supervisor_components",
        (
            "CREATE TABLE"
            " supervisor_components ("
            " name TEXT PRIMARY KEY,"
            " kind TEXT NOT NULL,"
            " state TEXT NOT NULL,"
            " max_restarts INTEGER"
            " NOT NULL,"
            " failures INTEGER NOT NULL"
            " DEFAULT 0,"
            " restarts INTEGER NOT NULL"
            " DEFAULT 0,"
            " last_reason TEXT,"
            " last_transition REAL"
            " NOT NULL)",
        ),
    ),
)


@dataclass(frozen=True)
class ComponentRecord:
    name: str
    kind: str
    state: str
    failures: int
    restarts: int
    max_restarts: int
    last_reason: str | None


class SupervisorEngine:
    """Lifecycle with restart budget."""

    def __init__(
        self,
        db: Database,
        clock: Clock,
        *,
        audit: AuditTrail,
    ) -> None:
        self._db = db
        self._clock = clock
        self._audit = audit
        MigrationRunner(
            db,
            "supervisor",
            _MIGRATIONS,
        ).run(clock)

    def _row(self, name: str) -> ComponentRecord:
        row = self._db.query_one(
            "SELECT * FROM"
            " supervisor_components"
            " WHERE name = ?",
            (name,),
        )
        if row is None:
            raise UnknownComponentError(
                f"unknown component:"
                f" {name}"
            )
        return ComponentRecord(
            name=str(row["name"]),
            kind=str(row["kind"]),
            state=str(row["state"]),
            failures=int(
                row["failures"]
            ),
            restarts=int(
                row["restarts"]
            ),
            max_restarts=int(
                row["max_restarts"]
            ),
            last_reason=(
                str(
                    row["last_reason"]
                )
                if row["last_reason"]
                is not None
                else None
            ),
        )

    def register(
        self,
        *,
        name: str,
        kind: str,
        max_restarts: int = 3,
    ) -> ComponentRecord:
        require_non_empty_str(
            name, "name"
        )
        require_non_empty_str(
            kind, "kind"
        )
        require_int_range(
            max_restarts,
            "max_restarts",
            1,
            100,
        )
        with (
            self._db.transaction()
            as cursor
        ):
            cursor.execute(
                "INSERT INTO"
                " supervisor_components"
                " (name, kind, state,"
                "  max_restarts,"
                "  last_transition)"
                " VALUES (?, ?, ?, ?, ?)"
                " ON CONFLICT(name) DO"
                " NOTHING",
                (
                    name,
                    kind,
                    STATE_REGISTERED,
                    max_restarts,
                    self._clock.now(),
                ),
            )
        return self._row(name)

    def mark_running(
        self, *, name: str
    ) -> ComponentRecord:
        current = self._row(name)
        if (
            current.state
            == STATE_QUARANTINED
        ):
            raise QuarantinedError(
                f"'{name}' is"
                " quarantined"
            )
        with (
            self._db.transaction()
            as cursor
        ):
            cursor.execute(
                "UPDATE"
                " supervisor_components"
                " SET state = ?,"
                " last_transition = ?"
                " WHERE name = ?",
                (
                    STATE_RUNNING,
                    self._clock.now(),
                    name,
                ),
            )
        return self._row(name)

    def mark_failed(
        self,
        *,
        name: str,
        reason: str,
    ) -> ComponentRecord:
        require_non_empty_str(
            reason, "reason"
        )
        with (
            self._db.transaction()
            as cursor
        ):
            cursor.execute(
                "UPDATE"
                " supervisor_components"
                " SET state = ?,"
                " failures = failures + 1,"
                " last_reason = ?,"
                " last_transition = ?"
                " WHERE name = ?",
                (
                    STATE_FAILED,
                    reason,
                    self._clock.now(),
                    name,
                ),
            )
        self._audit.append(
            event_type=(
                EVENT_SUPERVISOR_FAILED
            ),
            actor="supervisor",
            subject=name,
            payload={"reason": reason},
        )
        return self._row(name)

    def record_restart(
        self,
        *,
        name: str,
        actor: str,
    ) -> ComponentRecord:
        """One supervised restart; over budget
        the component is quarantined."""
        require_non_empty_str(
            actor, "actor"
        )
        current = self._row(name)
        restarts = (
            current.restarts + 1
        )
        if (
            restarts
            > current.max_restarts
        ):
            state = STATE_QUARANTINED
        else:
            state = STATE_RUNNING
        with (
            self._db.transaction()
            as cursor
        ):
            cursor.execute(
                "UPDATE"
                " supervisor_components"
                " SET state = ?,"
                " restarts = ?,"
                " last_transition = ?"
                " WHERE name = ?",
                (
                    state,
                    restarts,
                    self._clock.now(),
                    name,
                ),
            )
        self._audit.append(
            event_type=(
                EVENT_SUPERVISOR_RESTART
            ),
            actor=actor,
            subject=name,
            payload={
                "restarts": restarts,
                "state": state,
            },
        )
        record = self._row(name)
        if (
            record.state
            == STATE_QUARANTINED
        ):
            raise QuarantinedError(
                f"'{name}' exceeded"
                " restart budget"
                f" ({record.restarts}"
                ">"
                f"{record.max_restarts})"
                " - quarantined"
            )
        return record

    def snapshot(
        self,
    ) -> tuple[ComponentRecord, ...]:
        rows = self._db.query_all(
            "SELECT name FROM"
            " supervisor_components"
            " ORDER BY name"
        )
        return tuple(
            self._row(
                str(r["name"])
            )
            for r in rows
        )
