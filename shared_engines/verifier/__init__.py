"""Zyra public verifier: offline third-party authenticity."""
from __future__ import annotations

from shared_engines.verifier.verifier import (
    VerificationReport,
    verify_attestation_blob,
)

__all__ = ["VerificationReport", "verify_attestation_blob"]
