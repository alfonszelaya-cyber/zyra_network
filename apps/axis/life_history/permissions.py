"""Life History permissions - additive module."""
from __future__ import annotations

REGISTRY_OPERATORS = (
    "registrador_civil",
    "gobierno",
)
HISTORY_READERS = REGISTRY_OPERATORS + (
    "madre",
    "padre",
    "tutor",
    "medico",
    "policia",
    "abogado",
)
ZID_UPGRADERS = REGISTRY_OPERATORS + (
    "biometric-enroll",
)

__all__ = [
    "REGISTRY_OPERATORS",
    "HISTORY_READERS",
    "ZID_UPGRADERS",
]
