"""AI proofs: model registry, traceable analysis
provenance, unknown model and bad confidence
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
from shared_engines.ai.engine import AIEngine
from shared_engines.ai.engine import (
    UnknownModelError,
)


def _engine(tmp_path: Path) -> AIEngine:
    db = SQLiteAdapter(tmp_path / "ai.db")
    clock = FrozenClock()
    audit = AuditTrail(db, clock)
    outbox = Outbox(db, clock)
    outbox.ensure_schema()
    catalog = EventCatalog()
    catalog.register("ai.analysis.recorded")
    engine = AIEngine(
        db, clock, audit=audit, outbox=outbox
    )
    engine.register_model(
        model_id="doc-classifier",
        provider="external-lab",
        model_version="2.1.0",
        capabilities=(
            "document",
            "signature",
        ),
    )
    return engine


def test_analysis_provenance(
    tmp_path: Path,
) -> None:
    engine = _engine(tmp_path)
    sha = "a" * 64
    record = engine.record_analysis(
        model_id="doc-classifier",
        content_sha256=sha,
        verdict="authentic",
        confidence=0.93,
    )
    assert (
        record.model_version == "2.1.0"
    )
    history = engine.analysis_history(
        content_sha256=sha
    )
    assert len(history) == 1
    assert history[0].verdict == (
        "authentic"
    )


def test_unknown_and_bad_confidence(
    tmp_path: Path,
) -> None:
    engine = _engine(tmp_path)
    with pytest.raises(UnknownModelError):
        engine.record_analysis(
            model_id="ghost",
            content_sha256="b" * 64,
            verdict="x",
            confidence=0.5,
        )
    with pytest.raises(ValueError):
        engine.record_analysis(
            model_id="doc-classifier",
            content_sha256="b" * 64,
            verdict="x",
            confidence=1.5,
        )
    with pytest.raises(ValueError):
        engine.record_analysis(
            model_id="doc-classifier",
            content_sha256="b" * 64,
            verdict="x",
            confidence=-0.1,
        )


def test_history_per_content_isolated(
    tmp_path: Path,
) -> None:
    engine = _engine(tmp_path)
    engine.record_analysis(
        model_id="doc-classifier",
        content_sha256="c" * 64,
        verdict="authentic",
        confidence=0.9,
    )
    engine.record_analysis(
        model_id="doc-classifier",
        content_sha256="d" * 64,
        verdict="suspicious",
        confidence=0.4,
    )
    assert (
        len(
            engine.analysis_history(
                content_sha256="c"
                * 64
            )
        )
        == 1
    )
    assert (
        engine.analysis_history(
            content_sha256="d" * 64
        )[0].verdict
        == "suspicious"
    )
