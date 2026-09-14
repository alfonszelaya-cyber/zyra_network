"""Life History integration - server factory."""
from __future__ import annotations

from apps.axis.life_history.service import (
    LifeHistoryService,
)
from apps.axis.life_history.store import (
    LifeHistoryStore,
)


def build_life_history(
    *,
    db,
    clock,
    network_client,
    require_active_parents: bool = True,
) -> LifeHistoryService:
    store = LifeHistoryStore(db, clock)
    return LifeHistoryService(
        store=store,
        client=network_client,
        require_active_parents=(
            require_active_parents
        ),
    )
