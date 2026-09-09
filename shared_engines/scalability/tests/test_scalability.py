"""Scalability proofs: bounded admission with
BackpressureError, release, stable partitioning."""
from __future__ import annotations

from pathlib import Path

import pytest

from shared_engines.common.clocks import (
    FrozenClock,
)
from shared_engines.common.errors import (
    BackpressureError,
)
from shared_engines.scalability.engine import (
    ScalabilityEngine,
)
from shared_engines.scalability.errors import (
    CapacityNotDefinedError,
)
from shared_engines.storage.database import (
    SQLiteAdapter,
)


def _engine(tmp_path: Path) -> ScalabilityEngine:
    db = SQLiteAdapter(
        tmp_path / "scale.db"
    )
    clock = FrozenClock()
    return ScalabilityEngine(db, clock)


def test_admission_until_backpressure(
    tmp_path: Path,
) -> None:
    engine = _engine(tmp_path)
    engine.define_capacity(
        resource="queue-a", max_items=3
    )
    assert engine.admit(
        resource="queue-a"
    ).used == 1
    assert engine.admit(
        resource="queue-a"
    ).used == 2
    assert engine.admit(
        resource="queue-a"
    ).used == 3
    with pytest.raises(
        BackpressureError
    ):
        engine.admit(resource="queue-a")
    with pytest.raises(
        CapacityNotDefinedError
    ):
        engine.admit(resource="ghost")


def test_release_reopens_capacity(
    tmp_path: Path,
) -> None:
    engine = _engine(tmp_path)
    engine.define_capacity(
        resource="q", max_items=2
    )
    engine.admit(resource="q")
    engine.admit(resource="q")
    with pytest.raises(
        BackpressureError
    ):
        engine.admit(resource="q")
    freed = engine.release(
        resource="q", amount=1
    )
    assert freed.used == 1
    assert engine.admit(
        resource="q"
    ).used == 2


def test_partition_key_stable_and_ranged(
    tmp_path: Path,
) -> None:
    k1 = ScalabilityEngine.partition_key(
        entity_id="ZID-123",
        partitions=8,
    )
    k2 = ScalabilityEngine.partition_key(
        entity_id="ZID-123",
        partitions=8,
    )
    assert k1 == k2
    assert 0 <= k1 < 8
    spread = {
        ScalabilityEngine.partition_key(
            entity_id=f"e{i}",
            partitions=8,
        )
        for i in range(200)
    }
    assert len(spread) > 5
