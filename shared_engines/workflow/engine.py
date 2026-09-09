"""Workflow engine: durable multi-step runs with
compensation.

A workflow is an ordered list of named steps. A
run persists its position; each completed step is
durable. On failure, completed steps are
compensated in REVERSE order (saga pattern):

    RUNNING -> step -> step -> COMPLETED
        |
        v (failure)
    COMPENSATING (undo last-first)
        |
        v
    COMPENSATED

Every state change is durable (SQLite), emitted
to the Outbox, and lifecycle milestones are
audited. Reuses existing patterns only - no
parallel event system.
"""
from __future__ import annotations

import hashlib
import json
import sqlite3

from shared_engines.audit.chain import AuditTrail
from shared_engines.common.clocks import Clock
from shared_engines.common.identifiers import (
    new_id,
)
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
from shared_engines.workflow.contracts import (
    STATE_COMPENSATED,
    STATE_COMPENSATING,
    STATE_COMPLETED,
    STATE_RUNNING,
    WorkflowRun,
)
from shared_engines.workflow.errors import (
    InvalidStateError,
    UnknownRunError,
    UnknownWorkflowError,
)

EVENT_STARTED = "workflow.run.started"
EVENT_STEP = "workflow.run.step_completed"
EVENT_COMPLETED = "workflow.run.completed"
EVENT_FAILED = "workflow.run.failed"
EVENT_COMPENSATED = (
    "workflow.run.compensated"
)

_MIGRATIONS = (
    Migration(
        1,
        "workflow",
        (
            "CREATE TABLE workflow_defs ("
            " workflow_id TEXT PRIMARY KEY,"
            " steps_json TEXT NOT NULL,"
            " created_at REAL NOT NULL)",
            "CREATE TABLE workflow_runs ("
            " run_id TEXT PRIMARY KEY,"
            " workflow_id TEXT NOT NULL,"
            " state TEXT NOT NULL,"
            " current_step INTEGER NOT"
            " NULL DEFAULT 0,"
            " compensating_at INTEGER,"
            " reason TEXT,"
            " created_at REAL NOT NULL,"
            " updated_at REAL NOT NULL)",
        ),
    ),
)


class WorkflowEngine:
    """Durable saga-style workflow runs."""

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
            db, "workflow", _MIGRATIONS
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

    def _steps_of(
        self, workflow_id: str
    ) -> tuple[str, ...]:
        row = self._db.query_one(
            "SELECT steps_json FROM"
            " workflow_defs WHERE"
            " workflow_id = ?",
            (workflow_id,),
        )
        if row is None:
            raise UnknownWorkflowError(
                "unknown workflow:"
                f" {workflow_id}"
            )
        parsed = json.loads(
            str(row["steps_json"])
        )
        if not isinstance(parsed, list):
            return tuple()
        return tuple(
            str(s)
            for s in parsed
            if isinstance(s, str)
        )

    def _run_row(
        self, run_id: str
    ) -> sqlite3.Row:
        row = self._db.query_one(
            "SELECT * FROM workflow_runs"
            " WHERE run_id = ?",
            (run_id,),
        )
        if row is None:
            raise UnknownRunError(
                f"unknown run: {run_id}"
            )
        return row

    def _record(
        self, run_id: str
    ) -> WorkflowRun:
        row = self._run_row(run_id)
        steps = self._steps_of(
            str(row["workflow_id"])
        )
        comp = row["compensating_at"]
        state = str(row["state"])
        return WorkflowRun(
            run_id=str(row["run_id"]),
            workflow_id=str(
                row["workflow_id"]
            ),
            state=state,
            steps=steps,
            completed_count=int(
                row["current_step"]
            ),
            pending_compensations=(
                int(comp)
                if comp is not None
                and state
                == STATE_COMPENSATING
                else 0
            ),
            reason=(
                str(row["reason"])
                if row["reason"]
                is not None
                else None
            ),
        )

    def define_workflow(
        self,
        *,
        workflow_id: str,
        steps: tuple[str, ...],
    ) -> None:
        require_non_empty_str(
            workflow_id, "workflow_id"
        )
        if not steps:
            raise ValueError(
                "at least one step"
                " required"
            )
        if any(
            not s.strip()
            for s in steps
        ):
            raise ValueError(
                "steps must be non-empty"
            )
        with (
            self._db.transaction()
            as cursor
        ):
            cursor.execute(
                "INSERT INTO workflow_defs"
                " (workflow_id, steps_json,"
                "  created_at)"
                " VALUES (?, ?, ?)"
                " ON CONFLICT(workflow_id)"
                " DO UPDATE SET steps_json"
                " = excluded.steps_json",
                (
                    workflow_id,
                    canonical_json_dumps(
                        list(steps)
                    ),
                    self._clock.now(),
                ),
            )

    def start_run(
        self, *, workflow_id: str
    ) -> WorkflowRun:
        steps = self._steps_of(
            workflow_id
        )
        run_id = f"RUN-{new_id()}"
        now = self._clock.now()
        with (
            self._db.transaction()
            as cursor
        ):
            cursor.execute(
                "INSERT INTO workflow_runs"
                " (run_id, workflow_id,"
                "  state, current_step,"
                "  created_at, updated_at)"
                " VALUES (?, ?, ?, 0, ?, ?)",
                (
                    run_id,
                    workflow_id,
                    STATE_RUNNING,
                    now,
                    now,
                ),
            )
            self._emit(
                cursor,
                event_type=EVENT_STARTED,
                aggregate=run_id,
                payload={
                    "workflow": (
                        workflow_id
                    ),
                    "steps": len(steps),
                },
            )
        self._audit.append(
            event_type=EVENT_STARTED,
            actor="workflow-engine",
            subject=run_id,
            payload={
                "workflow": workflow_id
            },
        )
        return self._record(run_id)

    def complete_step(
        self, *, run_id: str
    ) -> WorkflowRun:
        row = self._run_row(run_id)
        if str(row["state"]) != (
            STATE_RUNNING
        ):
            raise InvalidStateError(
                "run is not RUNNING:"
                f" {run_id}"
            )
        workflow_id = str(
            row["workflow_id"]
        )
        steps = self._steps_of(
            workflow_id
        )
        current = int(
            row["current_step"]
        )
        if current >= len(steps):
            raise InvalidStateError(
                "no pending steps"
            )
        new_step = current + 1
        done = (
            new_step == len(steps)
        )
        now = self._clock.now()
        with (
            self._db.transaction()
            as cursor
        ):
            cursor.execute(
                "UPDATE workflow_runs SET"
                " current_step = ?,"
                " state = ?,"
                " updated_at = ?"
                " WHERE run_id = ?",
                (
                    new_step,
                    STATE_COMPLETED
                    if done
                    else STATE_RUNNING,
                    now,
                    run_id,
                ),
            )
            self._emit(
                cursor,
                event_type=(
                    EVENT_COMPLETED
                    if done
                    else EVENT_STEP
                ),
                aggregate=run_id,
                payload={
                    "step": steps[current],
                    "position": new_step,
                },
            )
        if done:
            self._audit.append(
                event_type=(
                    EVENT_COMPLETED
                ),
                actor="workflow-engine",
                subject=run_id,
                payload={},
            )
        return self._record(run_id)

    def fail_run(
        self,
        *,
        run_id: str,
        reason: str,
    ) -> WorkflowRun:
        require_non_empty_str(
            reason, "reason"
        )
        row = self._run_row(run_id)
        if str(row["state"]) != (
            STATE_RUNNING
        ):
            raise InvalidStateError(
                "run is not RUNNING:"
                f" {run_id}"
            )
        completed = int(
            row["current_step"]
        )
        terminal = (
            STATE_COMPENSATING
            if completed > 0
            else STATE_COMPENSATED
        )
        now = self._clock.now()
        with (
            self._db.transaction()
            as cursor
        ):
            cursor.execute(
                "UPDATE workflow_runs SET"
                " state = ?,"
                " compensating_at = ?,"
                " reason = ?,"
                " updated_at = ?"
                " WHERE run_id = ?",
                (
                    terminal,
                    completed
                    if terminal
                    == (
                        STATE_COMPENSATING
                    )
                    else None,
                    reason,
                    now,
                    run_id,
                ),
            )
            self._emit(
                cursor,
                event_type=EVENT_FAILED,
                aggregate=run_id,
                payload={
                    "reason": reason
                },
            )
        self._audit.append(
            event_type=EVENT_FAILED,
            actor="workflow-engine",
            subject=run_id,
            payload={"reason": reason},
        )
        return self._record(run_id)

    def compensate_step(
        self, *, run_id: str
    ) -> WorkflowRun:
        row = self._run_row(run_id)
        if str(row["state"]) != (
            STATE_COMPENSATING
        ):
            raise InvalidStateError(
                "run is not"
                " COMPENSATING:"
                f" {run_id}"
            )
        comp = int(
            row["compensating_at"]
            or 0
        )
        if comp <= 0:
            raise InvalidStateError(
                "nothing to compensate"
            )
        remaining = comp - 1
        done = remaining == 0
        now = self._clock.now()
        with (
            self._db.transaction()
            as cursor
        ):
            cursor.execute(
                "UPDATE workflow_runs SET"
                " compensating_at = ?,"
                " state = ?,"
                " updated_at = ?"
                " WHERE run_id = ?",
                (
                    remaining
                    if not done
                    else None,
                    STATE_COMPENSATED
                    if done
                    else (
                        STATE_COMPENSATING
                    ),
                    now,
                    run_id,
                ),
            )
            self._emit(
                cursor,
                event_type=(
                    EVENT_COMPENSATED
                    if done
                    else EVENT_STEP
                ),
                aggregate=run_id,
                payload={
                    "undo_position": comp
                },
            )
        if done:
            self._audit.append(
                event_type=(
                    EVENT_COMPENSATED
                ),
                actor="workflow-engine",
                subject=run_id,
                payload={},
            )
        return self._record(run_id)

    def get_run(
        self, *, run_id: str
    ) -> WorkflowRun:
        return self._record(run_id)
