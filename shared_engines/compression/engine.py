"""Compression engine: gzip with bomb guards.

Envelope is canonical JSON (zyra.comp.v1) carrying
the declared original size and the SHA-256 of the
plaintext. Decompression is STREAMING with a hard
output cap: a bomb cannot allocate memory beyond
the limit even if its header lies. Size and hash
are re-verified after inflation.

Pure utility layer: callers (engines above) are
responsible for auditing their own use of it.
"""
from __future__ import annotations

import base64
import gzip
import hashlib
import zlib
from dataclasses import dataclass

from shared_engines.common.errors import (
    IntegrityError,
)
from shared_engines.common.serialization import (
    canonical_json_dumps,
    canonical_json_loads,
)
from shared_engines.common.validation import (
    require_int_range,
)
from shared_engines.compression.errors import (
    CompressionLimitError,
    MalformedEnvelopeError,
)

_FORMAT = "zyra.comp.v1"
_ALGO = "gzip"
_STEP = 64 * 1024


@dataclass(frozen=True)
class CompressionResult:
    envelope: bytes
    original_size: int
    compressed_size: int
    sha256: str


class CompressionEngine:
    """Bounded gzip compress/decompress."""

    def __init__(
        self,
        *,
        max_input_bytes: int = 10_000_000,
        max_output_bytes: int = 50_000_000,
    ) -> None:
        require_int_range(
            max_input_bytes,
            "max_input_bytes",
            1,
            10**12,
            config=True,
        )
        require_int_range(
            max_output_bytes,
            "max_output_bytes",
            1,
            10**12,
            config=True,
        )
        self._max_in = max_input_bytes
        self._max_out = max_output_bytes

    def compress(
        self, data: bytes
    ) -> CompressionResult:
        if not data:
            raise ValueError(
                "data required"
            )
        if len(data) > self._max_in:
            raise CompressionLimitError(
                "input exceeds"
                f" {self._max_in} bytes"
            )
        compressed = gzip.compress(data)
        sha = hashlib.sha256(
            data
        ).hexdigest()
        envelope = canonical_json_dumps(
            {
                "format": _FORMAT,
                "algo": _ALGO,
                "original_size": len(
                    data
                ),
                "sha256": sha,
                "data": base64.b64encode(
                    compressed
                ).decode("ascii"),
            }
        ).encode("utf-8")
        return CompressionResult(
            envelope=envelope,
            original_size=len(data),
            compressed_size=len(
                envelope
            ),
            sha256=sha,
        )

    def decompress(
        self, envelope: bytes
    ) -> bytes:
        """Streaming inflate with hard cap;
        declared size + real size + hash all
        verified."""
        try:
            doc = canonical_json_loads(
                envelope.decode("utf-8")
            )
        except Exception as exc:
            raise (
                MalformedEnvelopeError(
                    "envelope not"
                    " decodable"
                )
            ) from exc
        if not isinstance(doc, dict) or (
            doc.get("format") != _FORMAT
            or doc.get("algo") != _ALGO
        ):
            raise (
                MalformedEnvelopeError(
                    "unknown envelope"
                    " format"
                )
            )
        declared = int(
            doc["original_size"]
        )
        if declared > self._max_out:
            raise CompressionLimitError(
                "declared size exceeds"
                f" {self._max_out} bytes"
            )
        compressed = base64.b64decode(
            str(doc["data"]),
            validate=True,
        )
        data = self._gunzip_limited(
            compressed
        )
        if len(data) != declared:
            raise IntegrityError(
                "size mismatch:"
                f" {len(data)} !="
                f" {declared}"
            )
        if (
            hashlib.sha256(
                data
            ).hexdigest()
            != doc["sha256"]
        ):
            raise IntegrityError(
                "sha256 mismatch after"
                " inflate"
            )
        return data

    def _gunzip_limited(
        self, compressed: bytes
    ) -> bytes:
        deco = zlib.decompressobj(wbits=31)
        out = bytearray()
        start = 0
        total = len(compressed)
        while start < total and not deco.eof:
            end = start + _STEP
            part = compressed[start:end]
            room = (
                self._max_out
                - len(out)
                + 1
            )
            out += deco.decompress(
                part, room
            )
            if len(out) > self._max_out:
                raise (
                    CompressionLimitError(
                        "inflated output"
                        " exceeds limit"
                    )
                )
            start = end
        while (
            not deco.eof
            and deco.unconsumed_tail
        ):
            room = (
                self._max_out
                - len(out)
                + 1
            )
            out += deco.decompress(
                deco.unconsumed_tail,
                room,
            )
            if len(out) > self._max_out:
                raise (
                    CompressionLimitError(
                        "inflated output"
                        " exceeds limit"
                    )
                )
        if not deco.eof:
            raise (
                MalformedEnvelopeError(
                    "truncated gzip"
                    " stream"
                )
            )
        return bytes(out)
