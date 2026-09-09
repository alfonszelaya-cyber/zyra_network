"""Workflow proofs: durable run to completion,
failure with reverse compensation, invalid ops
refused."""
from __future__ import annotations

from pathlib import Path

import pytest

from shared_engines.audit.chain import AuditTrail
from shared_engines.common.clocks import (
    FrozenClock,
)
from shared_engines.events.contracts import (
    EventCatalog,
)
from shared_engines.events.outbox import Outbox
from shared_engines.storage.database import (
    SQLiteAdapter,
)
from shared_engines.workflow.engine import (
    WorkflowEngine,
)
from shared_engines.workflow.errors import (
    InvalidStateError,
    UnknownRunError,
)


def _engine(
    tmp_path: Path,
) -> tuple[SQLiteAdapter, WorkflowEngine]:
    db = SQLiteAdapter(
        tmp_path / "wf.db"
    )
    clock = FrozenClock()
    audit = AuditTrail(db, clock)
    outbox = Outbox(db, clock)
    outbox.ensure_schema()
    catalog = EventCatalog()
    for et in (
        "workflow.run.started",
        "workflow.run.step_completed",
        "workflow.run.completed",
        "workflow.run.failed",
        "workflow.run.compensated",
    ):
        catalog.register(et)
    engine = WorkflowEngine(
        db,
        clock,
        audit=audit,
        outbox=outbox,
    )
    return db, engine


def test_run_to_completion(
    tmp_path: Path,
) -> None:
    db, engine = _engine(tmp_path)
    try:
        engine.define_workflow(
            workflow_id="onboarding",
            steps=(
                "verify-email",
                "kyc",
                "activate",
            ),
        )
        run = engine.start_run(
            workflow_id="onboarding"
        )
        assert run.state == "RUNNING"
        assert (
            run.completed_count == 0
        )
        r1 = engine.complete_step(
            run_id=run.run_id
        )
        assert (
            r1.completed_count == 1
        )
        assert r1.state == "RUNNING"
        engine.complete_step(
            run_id=run.run_id
        )
        final = engine.complete_step(
            run_id=run.run_id
        )
        assert (
            final.state == "COMPLETED"
        )
        assert (
            final.completed_count == 3
        )
        with pytest.raises(
            InvalidStateError
        ):
            engine.complete_step(
                run_id=run.run_id
            )
    finally:
        db.close()


def test_failure_compensates_reverse(
    tmp_path: Path,
) -> None:
    db, engine = _engine(tmp_path)
    try:
        engine.define_workflow(
            workflow_id="transfer",
            steps=(
                "debit",
                "transfer",
                "credit",
            ),
        )
        run = engine.start_run(
            workflow_id="transfer"
        )
        engine.complete_step(
            run_id=run.run_id
        )
        engine.complete_step(
            run_id=run.run_id
        )
        failed = engine.fail_run(
            run_id=run.run_id,
            reason="credit leg failed",
        )
        assert (
            failed.state
            == "COMPENSATING"
        )
        assert (
            failed.pending_compensations
            == 2
        )
        mid = engine.compensate_step(
            run_id=run.run_id
        )
        assert (
            mid.pending_compensations
            == 1
        )
        done = engine.compensate_step(
            run_id=run.run_id
        )
        assert (
            done.state
            == "COMPENSATED"
        )
        with pytest.raises(
            InvalidStateError
        ):
            engine.complete_step(
                run_id=run.run_id
            )
    finally:
        db.close()


def test_fail_without_steps_direct_compensated(
    tmp_path: Path,
) -> None:
    db, engine = _engine(tmp_path)
    try:
        engine.define_workflow(
            workflow_id="single",
            steps=("only",),
        )
        run = engine.start_run(
            workflow_id="single"
        )
        failed = engine.fail_run(
            run_id=run.run_id,
            reason="early",
        )
        assert (
            failed.state
            == "COMPENSATED"
        )
        with pytest.raises(
            UnknownRunError
        ):
            engine.get_run(
                run_id="RUN-ghost"
            )
        with pytest.raises(ValueError):
            engine.define_workflow(
                workflow_id="empty",
                steps=(),
            )
    finally:
        db.close()
