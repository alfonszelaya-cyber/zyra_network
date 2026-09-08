"""Integrity proofs: deterministic digests,
streaming file hashing, tamper detection and
unknown-proof errors."""
from __future__ import annotations

import hashlib
from pathlib import Path

import pytest

from shared_engines.common.clocks import (
    FrozenClock,
)
from shared_engines.common.errors import (
    NotFoundError,
)
from shared_engines.integrity.engine import (
    IntegrityEngine,
)
from shared_engines.integrity.errors import (
    UnsupportedAlgorithmError,
)
from shared_engines.storage.database import (
    SQLiteAdapter,
)


def _engine(
    tmp_path: Path,
) -> tuple[
    SQLiteAdapter,
    IntegrityEngine,
    FrozenClock,
]:
    db = SQLiteAdapter(
        tmp_path / "integrity.db"
    )
    clock = FrozenClock()
    engine = IntegrityEngine(db, clock)
    return db, engine, clock


def test_deterministic_digest(
    tmp_path: Path,
) -> None:
    db, engine, clock = _engine(tmp_path)
    try:
        d1 = engine.digest_bytes(
            b"zyra network"
        )
        d2 = engine.digest_bytes(
            b"zyra network"
        )
        assert d1 == d2
        assert (
            d1
            == hashlib.sha256(
                b"zyra network"
            ).hexdigest()
        )
        d3 = engine.digest_bytes(
            b"zyra network "
        )
        assert d3 != d1
    finally:
        db.close()


def test_file_digest_streams(
    tmp_path: Path,
) -> None:
    db, engine, clock = _engine(tmp_path)
    try:
        blob = tmp_path / "doc.bin"
        payload = (
            b"patient record" * 10_000
        )
        blob.write_bytes(payload)
        assert (
            engine.digest_file(blob)
            == hashlib.sha256(
                payload
            ).hexdigest()
        )
    finally:
        db.close()


def test_issue_and_verify_detects_tampering(
    tmp_path: Path,
) -> None:
    db, engine, clock = _engine(tmp_path)
    try:
        original = (
            b"birth record: Bebe Perez"
        )
        proof = engine.issue_proof(
            subject="doc-1",
            data=original,
        )
        assert (
            engine.verify_proof(
                proof_id=proof.proof_id,
                data=original,
            )
            is True
        )
        altered = (
            b"birth record: Faked Name"
        )
        assert (
            engine.verify_proof(
                proof_id=proof.proof_id,
                data=altered,
            )
            is False
        )
        assert (
            engine.verify_latest(
                subject="doc-1",
                data=original,
            )
            is True
        )
        assert (
            engine.verify_latest(
                subject="doc-1",
                data=altered,
            )
            is False
        )
    finally:
        db.close()


def test_unknown_proof_and_algorithm(
    tmp_path: Path,
) -> None:
    db, engine, clock = _engine(tmp_path)
    try:
        with pytest.raises(
            NotFoundError
        ):
            engine.verify_proof(
                proof_id="PRF-nope",
                data=b"x",
            )
        with pytest.raises(
            NotFoundError
        ):
            engine.verify_latest(
                subject="ghost",
                data=b"x",
            )
        with pytest.raises(
            UnsupportedAlgorithmError
        ):
            IntegrityEngine(
                db,
                clock,
                algorithm="md5",
            )
        sha512_engine = IntegrityEngine(
            db, clock, algorithm="sha512"
        )
        d = sha512_engine.digest_bytes(
            b"x"
        )
        assert (
            d
            == hashlib.sha512(
                b"x"
            ).hexdigest()
        )
    finally:
        db.close()
