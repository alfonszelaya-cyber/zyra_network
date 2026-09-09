"""Interoperability proofs: mutual version
negotiation, refusal, schema retrieval."""
from __future__ import annotations

from pathlib import Path

import pytest

from shared_engines.common.clocks import (
    FrozenClock,
)
from shared_engines.common.errors import (
    UnsupportedVersionError,
)
from shared_engines.interoperability.engine import (
    InteroperabilityEngine,
    SchemaNotFoundError,
)
from shared_engines.storage.database import (
    SQLiteAdapter,
)


def _engine(
    tmp_path: Path,
) -> InteroperabilityEngine:
    db = SQLiteAdapter(
        tmp_path / "interop.db"
    )
    clock = FrozenClock()
    engine = InteroperabilityEngine(
        db, clock
    )
    engine.register_schema(
        schema_id="zyra.identity.v1",
        version=1,
        definition="identity schema v1",
    )
    engine.register_schema(
        schema_id="zyra.identity.v1",
        version=2,
        definition="identity schema v2",
    )
    engine.register_schema(
        schema_id="zyra.identity.v1",
        version=3,
        definition="identity schema v3",
    )
    return engine


def test_negotiation_picks_highest_mutual(
    tmp_path: Path,
) -> None:
    engine = _engine(tmp_path)
    result = engine.negotiate(
        schema_id="zyra.identity.v1",
        client_versions=(1, 2),
    )
    assert result.agreed_version == 2
    result = engine.negotiate(
        schema_id="zyra.identity.v1",
        client_versions=(3, 4),
    )
    assert result.agreed_version == 3


def test_no_mutual_version_refused(
    tmp_path: Path,
) -> None:
    engine = _engine(tmp_path)
    with pytest.raises(
        UnsupportedVersionError
    ):
        engine.negotiate(
            schema_id="zyra.identity.v1",
            client_versions=(7, 8),
        )
    with pytest.raises(
        UnsupportedVersionError
    ):
        engine.negotiate(
            schema_id="zyra.identity.v1",
            client_versions=(),
        )


def test_get_and_unknown(
    tmp_path: Path,
) -> None:
    engine = _engine(tmp_path)
    schema = engine.get_schema(
        schema_id="zyra.identity.v1",
        version=2,
    )
    assert (
        schema.definition
        == "identity schema v2"
    )
    with pytest.raises(
        SchemaNotFoundError
    ):
        engine.get_schema(
            schema_id="ghost",
            version=1,
        )
    with pytest.raises(
        SchemaNotFoundError
    ):
        engine.negotiate(
            schema_id="ghost",
            client_versions=(1,),
        )
