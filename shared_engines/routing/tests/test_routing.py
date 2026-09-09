"""Routing proofs: priority resolution, failover
by deactivation, unknown key refused."""
from __future__ import annotations

from pathlib import Path

import pytest

from shared_engines.common.clocks import (
    FrozenClock,
)
from shared_engines.routing.engine import (
    RoutingEngine,
)
from shared_engines.routing.errors import (
    NoRouteError,
)
from shared_engines.storage.database import (
    SQLiteAdapter,
)


def _engine(tmp_path: Path) -> RoutingEngine:
    db = SQLiteAdapter(
        tmp_path / "routes.db"
    )
    clock = FrozenClock()
    return RoutingEngine(db, clock)


def test_priority_resolution(
    tmp_path: Path,
) -> None:
    engine = _engine(tmp_path)
    engine.register_route(
        route_key="verify.docs",
        target="node-a",
        priority=10,
    )
    engine.register_route(
        route_key="verify.docs",
        target="node-b",
        priority=5,
    )
    engine.register_route(
        route_key="verify.docs",
        target="node-c",
        priority=1,
    )
    best = engine.resolve(
        route_key="verify.docs"
    )
    assert best.target == "node-c"
    assert best.priority == 1
    all_routes = engine.list_routes(
        route_key="verify.docs"
    )
    assert len(all_routes) == 3


def test_deactivation_falls_to_next(
    tmp_path: Path,
) -> None:
    engine = _engine(tmp_path)
    primary = engine.register_route(
        route_key="pay.settle",
        target="primary",
        priority=1,
    )
    engine.register_route(
        route_key="pay.settle",
        target="backup",
        priority=2,
    )
    assert (
        engine.resolve(
            route_key="pay.settle"
        ).target
        == "primary"
    )
    engine.deactivate_route(
        route_id=primary.route_id
    )
    fell = engine.resolve(
        route_key="pay.settle"
    )
    assert fell.target == "backup"
    assert fell.active is True
    assert (
        engine.resolve(
            route_key="pay.settle"
        ).priority
        == 2
    )


def test_unknown_key_refused(
    tmp_path: Path,
) -> None:
    engine = _engine(tmp_path)
    with pytest.raises(NoRouteError):
        engine.resolve(
            route_key="ghost.key"
        )
