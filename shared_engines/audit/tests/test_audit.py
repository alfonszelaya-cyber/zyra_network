from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

import pytest

from shared_engines.audit.chain import AuditTrail
from shared_engines.common.clocks import FrozenClock
from shared_engines.common.errors import IntegrityError, ValidationError
from shared_engines.storage.database import SQLiteAdapter


def _trail(tmp_path: Path) -> tuple[AuditTrail, SQLiteAdapter]:
    db = SQLiteAdapter(tmp_path / "audit.db")
    return AuditTrail(db, FrozenClock()), db


def test_chain_verifies_and_detects_tampering(tmp_path: Path) -> None:
    trail, db = _trail(tmp_path)
    for index in range(3):
        trail.append(
            event_type="test.event",
            actor="tester",
            subject=f"s{index}",
            payload={"i": index},
        )
    assert trail.verify() == 3
    db.execute(
        "UPDATE audit_records SET event_type = 'evil'"
        " WHERE sequence = 2"
    )
    with pytest.raises(IntegrityError):
        trail.verify()
    db.close()


def test_chain_detects_row_deletion(tmp_path: Path) -> None:
    trail, db = _trail(tmp_path)
    for index in range(3):
        trail.append(
            event_type="t", actor="a", subject=f"s{index}", payload={}
        )
    db.execute("DELETE FROM audit_records WHERE sequence = 2")
    with pytest.raises(IntegrityError):
        trail.verify()
    db.close()


def test_checkpoint_binds_chain(tmp_path: Path) -> None:
    trail, db = _trail(tmp_path)
    trail.append(event_type="t", actor="a", subject="s", payload={"n": 1})
    sequence, checkpoint_hash = trail.checkpoint()
    assert sequence == 1
    assert len(checkpoint_hash) == 64
    trail.append(event_type="t", actor="a", subject="s2", payload={})
    assert trail.verify_checkpoints() == 1
    db.execute(
        "UPDATE audit_records SET subject = 'rewritten'"
        " WHERE sequence = 1"
    )
    with pytest.raises(IntegrityError):
        trail.verify_checkpoints()
    db.close()


def test_checkpoint_requires_records(tmp_path: Path) -> None:
    trail, _ = _trail(tmp_path)
    with pytest.raises(ValidationError):
        trail.checkpoint()


def test_chain_gap_free_under_concurrency(tmp_path: Path) -> None:
    trail, db = _trail(tmp_path)

    def write(index: int) -> None:
        trail.append(
            event_type="t",
            actor="worker",
            subject=f"s{index}",
            payload={"i": index},
        )

    with ThreadPoolExecutor(max_workers=4) as pool:
        list(pool.map(write, range(24)))
    assert trail.verify() == 24
    db.close()
