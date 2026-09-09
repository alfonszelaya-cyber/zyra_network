"""Supervisor proofs: lifecycle with audit,
restart budget to quarantine, unknown refused."""
from __future__ import annotations

from pathlib import Path

import pytest

from shared_engines.audit.chain import AuditTrail
from shared_engines.common.clocks import (
    FrozenClock,
)
from shared_engines.storage.database import (
    SQLiteAdapter,
)
from shared_engines.supervisor.engine import (
    SupervisorEngine,
)
from shared_engines.supervisor.errors import (
    QuarantinedError,
    UnknownComponentError,
)


def _engine(
    tmp_path: Path,
) -> tuple[SQLiteAdapter, SupervisorEngine]:
    db = SQLiteAdapter(
        tmp_path / "sup.db"
    )
    clock = FrozenClock()
    audit = AuditTrail(db, clock)
    return db, SupervisorEngine(
        db, clock, audit=audit
    )


def test_lifecycle_with_audit(
    tmp_path: Path,
) -> None:
    db, engine = _engine(tmp_path)
    try:
        comp = engine.register(
            name="engine-x",
            kind="worker",
            max_restarts=3,
        )
        assert comp.state == "REGISTERED"
        running = engine.mark_running(
            name="engine-x"
        )
        assert running.state == "RUNNING"
        failed = engine.mark_failed(
            name="engine-x",
            reason="socket hangup",
        )
        assert failed.state == "FAILED"
        assert failed.failures == 1
        restarted = (
            engine.record_restart(
                name="engine-x",
                actor="ops",
            )
        )
        assert (
            restarted.state == "RUNNING"
        )
        assert restarted.restarts == 1
        assert engine.mark_failed(
            name="engine-x",
            reason="again",
        ).failures == 2
        entries = engine.snapshot()
        assert len(entries) == 1
    finally:
        db.close()


def test_restart_budget_quarantines(
    tmp_path: Path,
) -> None:
    db, engine = _engine(tmp_path)
    try:
        engine.register(
            name="flaky",
            kind="worker",
            max_restarts=2,
        )
        engine.mark_running(name="flaky")
        for round_no in range(2):
            engine.mark_failed(
                name="flaky",
                reason=(
                    f"crash-{round_no}"
                ),
            )
            record = (
                engine.record_restart(
                    name="flaky",
                    actor="ops",
                )
            )
            assert (
                record.state == "RUNNING"
            )
        engine.mark_failed(
            name="flaky",
            reason="final crash",
        )
        with pytest.raises(
            QuarantinedError
        ):
            engine.record_restart(
                name="flaky",
                actor="ops",
            )
        record = engine.snapshot()[0]
        assert (
            record.state
            == "QUARANTINED"
        )
        with pytest.raises(
            QuarantinedError
        ):
            engine.mark_running(
                name="flaky"
            )
    finally:
        db.close()


def test_unknown_component_refused(
    tmp_path: Path,
) -> None:
    db, engine = _engine(tmp_path)
    try:
        with pytest.raises(
            UnknownComponentError
        ):
            engine.mark_running(
                name="ghost"
            )
        with pytest.raises(
            UnknownComponentError
        ):
            engine.mark_failed(
                name="ghost",
                reason="x",
            )
    finally:
        db.close()
