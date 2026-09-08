"""Encryption engine proofs: zyra.enc.v1 reuse,
AAD binding, tamper detection via existing typed
error, and DURABLE rotation across restarts."""
from __future__ import annotations

from pathlib import Path

import pytest

from shared_engines.common.clocks import (
    FrozenClock,
)
from shared_engines.common.errors import (
    IntegrityError,
)
from shared_engines.encryption.engine import (
    EncryptionEngine,
)
from shared_engines.storage.database import (
    SQLiteAdapter,
)

_FORMAT = b"zyra.enc.v1"


def _db(
    tmp_path: Path, name: str
) -> SQLiteAdapter:
    return SQLiteAdapter(
        tmp_path / f"{name}.db"
    )


def test_seal_uses_existing_format(
    tmp_path: Path,
) -> None:
    db = _db(tmp_path, "a")
    try:
        engine = EncryptionEngine(
            db, FrozenClock()
        )
        sealed = engine.seal(
            b"expediente confidencial"
        )
        assert (
            _FORMAT in sealed
        )
        assert (
            engine.open(sealed)
            == (
                b"expediente"
                b" confidencial"
            )
        )
        assert (
            engine.inspect_key_version(
                sealed
            )
            == 1
        )
    finally:
        db.close()


def test_aad_binding_and_tamper(
    tmp_path: Path,
) -> None:
    db = _db(tmp_path, "b")
    try:
        engine = EncryptionEngine(
            db, FrozenClock()
        )
        sealed = engine.seal(
            b"data",
            aad=b"record-42",
        )
        assert (
            engine.open(
                sealed,
                aad=b"record-42",
            )
            == b"data"
        )
        with pytest.raises(
            IntegrityError
        ):
            engine.open(sealed)
        tampered = bytearray(sealed)
        tampered[-3] ^= 0xFF
        with pytest.raises(
            IntegrityError
        ):
            engine.open(
                bytes(tampered),
                aad=b"record-42",
            )
    finally:
        db.close()


def test_rotation_is_durable_across_restart(
    tmp_path: Path,
) -> None:
    db = _db(tmp_path, "c")
    try:
        clock = FrozenClock()
        engine = EncryptionEngine(
            db, clock
        )
        old = engine.seal(b"v1 secret")
        assert (
            engine.inspect_key_version(
                old
            )
            == 1
        )
        new_version = engine.rotate()
        assert new_version == 2
        new = engine.seal(b"v2 secret")
        assert (
            engine.inspect_key_version(
                new
            )
            == 2
        )
        # RESTART: fresh engine, same DB
        engine2 = EncryptionEngine(
            db, FrozenClock()
        )
        assert (
            engine2.open(old)
            == b"v1 secret"
        )
        assert (
            engine2.open(new)
            == b"v2 secret"
        )
        states = [
            (r.version, r.state)
            for r in (
                engine2.key_history()
            )
        ]
        assert states == [
            (1, "RETIRED"),
            (2, "ACTIVE"),
        ]
    finally:
        db.close()


def test_reseal_upgrades_version(
    tmp_path: Path,
) -> None:
    db = _db(tmp_path, "d")
    try:
        engine = EncryptionEngine(
            db, FrozenClock()
        )
        v1 = engine.seal(b"legacy")
        engine.rotate()
        upgraded = engine.reseal(v1)
        assert (
            engine.inspect_key_version(
                upgraded
            )
            == 2
        )
        assert (
            engine.open(upgraded)
            == b"legacy"
        )
    finally:
        db.close()
