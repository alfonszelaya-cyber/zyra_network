"""Typed integrity errors."""
from __future__ import annotations

from shared_engines.common.errors import (
    EngineError,
)


class UnsupportedAlgorithmError(
    EngineError
):
    """Requested digest algorithm is not
    available."""


class ProofNotFoundError(EngineError):
    """No proof stored for the subject."""
