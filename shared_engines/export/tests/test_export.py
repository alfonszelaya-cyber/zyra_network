"""Export proofs: signed bundle, offline third-
party verification, tamper detection."""
from __future__ import annotations

import json
from pathlib import Path

import pytest

from shared_engines.audit.chain import AuditTrail
from shared_engines.common.clocks import (
    FrozenClock,
)
from shared_engines.common.serialization import (
    canonical_json_dumps,
)
from shared_engines.events.outbox import Outbox
from shared_engines.export.engine import (
    ExportEngine,
)
from shared_engines.network.portable_profile import (
    ProfileRegistry,
)
from shared_engines.storage.database import (
    SQLiteAdapter,
)
from shared_engines.verification.signatures import (
    Ed25519Signer,
)


def _engine(
    tmp_path: Path,
) -> tuple[SQLiteAdapter, ExportEngine]:
    db = SQLiteAdapter(
        tmp_path / "export.db"
    )
    clock = FrozenClock()
    audit = AuditTrail(db, clock)
    outbox = Outbox(db, clock)
    outbox.ensure_schema()
    profiles = ProfileRegistry(
        db,
        clock,
        audit=audit,
        outbox=outbox,
    )
    profiles.register_app(
        app_id="portal",
        display_name="Portal",
        scopes=("display_name",),
    )
    signer, _ = Ed25519Signer.generate()
    engine = ExportEngine(
        db,
        clock,
        signer=signer,
        audit=audit,
    )
    return db, engine


def test_export_and_offline_verify(
    tmp_path: Path,
) -> None:
    db, engine = _engine(tmp_path)
    try:
        bundle = engine.export_bundle(
            subject_zid="ZID-1",
            entries=(
                (
                    "credential",
                    "CRD-1",
                    "titulo",
                ),
                (
                    "history",
                    "H-1",
                    "nacimiento",
                ),
            ),
            actor_app="portal",
        )
        assert (
            engine.verify_stored(
                bundle_id=(
                    bundle.bundle_id
                )
            )
            is True
        )
        assert (
            ExportEngine.verify_offline(
                bundle_id=(
                    bundle.bundle_id
                ),
                entries_json=(
                    bundle.entries_json
                ),
                signature=(
                    bundle.signature
                ),
                public_pem=(
                    bundle.public_pem
                ),
            )
            is True
        )
    finally:
        db.close()


def test_tampered_entries_detected(
    tmp_path: Path,
) -> None:
    db, engine = _engine(tmp_path)
    try:
        bundle = engine.export_bundle(
            subject_zid="ZID-1",
            entries=(
                ("doc", "D-1", "original"),
            ),
            actor_app="portal",
        )
        doc = json.loads(
            bundle.entries_json.decode(
                "utf-8"
            )
        )
        doc[0]["content"] = "FALSIFICADO"
        fake = canonical_json_dumps(
            doc
        ).encode("utf-8")
        assert (
            ExportEngine.verify_offline(
                bundle_id=(
                    bundle.bundle_id
                ),
                entries_json=fake,
                signature=(
                    bundle.signature
                ),
                public_pem=(
                    bundle.public_pem
                ),
            )
            is False
        )
    finally:
        db.close()


def test_unregistered_app_and_empty(
    tmp_path: Path,
) -> None:
    db, engine = _engine(tmp_path)
    try:
        with pytest.raises(
            PermissionError
        ):
            engine.export_bundle(
                subject_zid="ZID-1",
                entries=(
                    ("doc", "D", "c"),
                ),
                actor_app="malware",
            )
        with pytest.raises(Exception):
            engine.export_bundle(
                subject_zid="ZID-1",
                entries=(),
                actor_app="portal",
            )
    finally:
        db.close()
