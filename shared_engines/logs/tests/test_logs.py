from __future__ import annotations

from pathlib import Path

import pytest

from shared_engines.common.clocks import FrozenClock
from shared_engines.common.errors import IntegrityError
from shared_engines.logs.structured import (
    CorrelationContext,
    StructuredLogger,
)
from shared_engines.storage.database import SQLiteAdapter


def test_log_roundtrip_with_correlation(tmp_path: Path) -> None:
    db = SQLiteAdapter(tmp_path / "logs.db")
    logger = StructuredLogger(db, FrozenClock())
    ctx = CorrelationContext()
    corr = ctx.start()
    record = logger.info(
        component="identity",
        message="registered new identity",
        correlation_id=corr,
        detail={"zid": "ZID-abc", "kind": "person"},
    )
    assert record.level == "INFO"
    assert record.correlation_id == corr
    assert record.detail["zid"] == "ZID-abc"
    trace = logger.query_by_correlation(corr)
    assert len(trace) == 1
    db.close()


def test_correlation_groups_multi_operation_trace(
    tmp_path: Path,
) -> None:
    db = SQLiteAdapter(tmp_path / "logs.db")
    logger = StructuredLogger(db, FrozenClock())
    ctx = CorrelationContext()
    corr = ctx.start()
    logger.info("api", "request received", corr)
    logger.info("identity", "identity looked up", corr)
    logger.warning("verification", "doc hash mismatch", corr)
    logger.error("api", "request failed", corr)
    trace = logger.query_by_correlation(corr)
    assert len(trace) == 4
    levels = [r.level for r in trace]
    assert levels == ["INFO", "INFO", "WARNING", "ERROR"]
    components = [r.component for r in trace]
    assert components == [
        "api",
        "identity",
        "verification",
        "api",
    ]
    db.close()


def test_invalid_level_rejected(tmp_path: Path) -> None:
    db = SQLiteAdapter(tmp_path / "logs.db")
    logger = StructuredLogger(db, FrozenClock())
    with pytest.raises(IntegrityError):
        logger.log(
            level="VERBOSE",
            component="x",
            message="y",
            correlation_id="REQ-1",
        )
    db.close()


def test_retention_keeps_newest(tmp_path: Path) -> None:
    db = SQLiteAdapter(tmp_path / "logs.db")
    clock = FrozenClock()
    logger = StructuredLogger(db, clock)
    for index in range(10):
        logger.info("test", f"line {index}", f"REQ-{index}")
        clock.advance(1)
    removed = logger.enforce_retention(keep=3)
    assert removed == 7
    db.close()


def test_logs_survive_reopen(tmp_path: Path) -> None:
    path = tmp_path / "logs.db"
    db = SQLiteAdapter(path)
    logger = StructuredLogger(db, FrozenClock())
    logger.info("test", "persist me", "REQ-42")
    db.close()
    db2 = SQLiteAdapter(path)
    logger2 = StructuredLogger(db2, FrozenClock())
    trace = logger2.query_by_correlation("REQ-42")
    assert len(trace) == 1
    assert trace[0].message == "persist me"
    db2.close()
