"""System loader proofs: manifest-governed loading,
compatibility policy enforced, duplicate and
unknown refused, unload and reload."""
from __future__ import annotations

from pathlib import Path

import pytest

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
from shared_engines.system_loader.engine import (
    SystemLoaderEngine,
)
from shared_engines.system_loader.errors import (
    ComponentAlreadyLoadedError,
    IncompatibleVersionError,
    ManifestNotRegisteredError,
    UnknownLoadedComponentError,
)


def _engine(
    tmp_path: Path,
    *,
    contract: int = 1,
) -> SystemLoaderEngine:
    db = SQLiteAdapter(
        tmp_path
        / f"loader{contract}.db"
    )
    clock = FrozenClock()
    outbox = Outbox(db, clock)
    outbox.ensure_schema()
    catalog = EventCatalog()
    catalog.register(
        "system.component.loaded"
    )
    catalog.register(
        "system.component.unloaded"
    )
    return SystemLoaderEngine(
        db,
        clock,
        outbox=outbox,
        network_contract_version=contract,
    )


def test_compatible_load(tmp_path: Path) -> None:
    engine = _engine(tmp_path)
    engine.register_manifest(
        component_id="engine-search",
        version=2,
        min_contract=1,
        max_contract=2,
    )
    loaded = engine.load_component(
        component_id="engine-search"
    )
    assert loaded.version == 2
    names = {
        c.component_id
        for c in (
            engine.loaded_components()
        )
    }
    assert "engine-search" in names


def test_incompatible_and_unknown_refused(
    tmp_path: Path,
) -> None:
    engine = _engine(
        tmp_path, contract=1
    )
    engine.register_manifest(
        component_id="future-engine",
        version=1,
        min_contract=3,
        max_contract=5,
    )
    with pytest.raises(
        IncompatibleVersionError
    ):
        engine.load_component(
            component_id="future-engine"
        )
    with pytest.raises(
        ManifestNotRegisteredError
    ):
        engine.load_component(
            component_id="ghost"
        )


def test_duplicate_unload_reload(
    tmp_path: Path,
) -> None:
    engine = _engine(tmp_path)
    engine.register_manifest(
        component_id="engine-x",
        version=1,
        min_contract=1,
        max_contract=1,
    )
    engine.load_component(
        component_id="engine-x"
    )
    with pytest.raises(
        ComponentAlreadyLoadedError
    ):
        engine.load_component(
            component_id="engine-x"
        )
    unloaded = (
        engine.unload_component(
            component_id="engine-x"
        )
    )
    assert unloaded.version == 1
    assert (
        engine.loaded_components()
        == ()
    )
    with pytest.raises(
        UnknownLoadedComponentError
    ):
        engine.unload_component(
            component_id="engine-x"
        )
    reloaded = engine.load_component(
        component_id="engine-x"
    )
    assert reloaded.version == 1
