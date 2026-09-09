"""Typed compression errors."""
from __future__ import annotations

from shared_engines.common.errors import (
    EngineError,
    IntegrityError,
)


class CompressionLimitError(EngineError):
    """Input or output exceeds configured
    limits (decompression-bomb guard)."""


class MalformedEnvelopeError(
    IntegrityError
):
    """Envelope is not a valid Zyra
    compression envelope."""
