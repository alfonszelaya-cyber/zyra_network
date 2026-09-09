"""Compression proofs: roundtrip, bomb guard,
corrupted envelope."""
from __future__ import annotations

import gzip

import pytest

from shared_engines.common.errors import (
    IntegrityError,
)
from shared_engines.compression.engine import (
    CompressionEngine,
)
from shared_engines.compression.errors import (
    CompressionLimitError,
    MalformedEnvelopeError,
)


def test_roundtrip_and_sizes() -> None:
    engine = CompressionEngine()
    data = b"expediente completo" * 1000
    result = engine.compress(data)
    assert (
        result.original_size == len(data)
    )
    assert (
        result.compressed_size
        < len(data)
    )
    assert (
        engine.decompress(
            result.envelope
        )
        == data
    )


def test_bomb_guard() -> None:
    small = CompressionEngine(
        max_input_bytes=1_000_000,
        max_output_bytes=100_000,
    )
    bomb = b"\x00" * 1_000_000
    tiny = b"\x00" * 500_000
    envelope = small.compress(tiny)
    with pytest.raises(
        CompressionLimitError
    ):
        small.decompress(
            envelope.envelope
        )
    bigger = b"\x00" * 2_000_000
    with pytest.raises(
        CompressionLimitError
    ):
        small.compress(bigger)
    assert len(gzip.compress(bomb)) < 10_000


def test_corrupted_envelope() -> None:
    engine = CompressionEngine()
    with pytest.raises(
        MalformedEnvelopeError
    ):
        engine.decompress(b"not-json")
    result = engine.compress(b"data")
    broken = (
        result.envelope[:-4]
        + b'????}'
    )
    with pytest.raises(IntegrityError):
        engine.decompress(broken)
