"""Compliance proofs: mandatory vs optional,
unknown policy refused, decisions audited."""
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
from shared_engines.compliance.engine import (
    ComplianceEngine,
    PolicyNotFoundError,
)


def _engine(
    tmp_path: Path,
) -> tuple[ComplianceEngine, AuditTrail]:
    db = SQLiteAdapter(
        tmp_path / "comp.db"
    )
    clock = FrozenClock()
    audit = AuditTrail(db, clock)
    outbox = Outbox(db, clock)
    outbox.ensure_schema()
    catalog = EventCatalog()
    catalog.register(
        "compliance.decision.recorded"
    )
    engine = ComplianceEngine(
        db,
        clock,
        audit=audit,
        outbox=outbox,
    )
    engine.register_policy(
        jurisdiction="SV",
        requirement="kyc_verified",
        mandatory=True,
    )
    return engine, audit


def test_mandatory_satisfied(
    tmp_path: Path,
) -> None:
    engine, audit = _engine(tmp_path)
    decision = engine.evaluate(
        subject_zid="ZID-1",
        jurisdiction="SV",
        requirement="kyc_verified",
        satisfied=True,
    )
    assert decision.compliant is True
    assert audit.verify() >= 1


def test_mandatory_unmet_denied(
    tmp_path: Path,
) -> None:
    engine, audit = _engine(tmp_path)
    decision = engine.evaluate(
        subject_zid="ZID-1",
        jurisdiction="SV",
        requirement="kyc_verified",
        satisfied=False,
    )
    assert decision.compliant is False
    assert audit.verify() >= 1


def test_optional_unmet_allowed(
    tmp_path: Path,
) -> None:
    engine, audit = _engine(tmp_path)
    engine.register_policy(
        jurisdiction="SV",
        requirement="phone_confirmed",
        mandatory=False,
    )
    decision = engine.evaluate(
        subject_zid="ZID-1",
        jurisdiction="SV",
        requirement="phone_confirmed",
        satisfied=False,
    )
    assert decision.compliant is True
    assert audit.verify() >= 1


def test_unknown_policy(
    tmp_path: Path,
) -> None:
    engine, audit = _engine(tmp_path)
    with pytest.raises(
        PolicyNotFoundError
    ):
        engine.evaluate(
            subject_zid="ZID-1",
            jurisdiction="XX",
            requirement="ghost",
            satisfied=True,
        )
    assert audit.verify() >= 0
