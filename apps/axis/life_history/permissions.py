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


def authorize(*args, **kwargs):
    action = kwargs.get("action")
    if action is None and args:
        action = args[0]
    role = kwargs.get("role")
    if role is None and len(args) >= 2:
        role = args[1]
    role = (role or "").strip()
    if not role:
        return False
    if action == "history.read":
        return role in HISTORY_READERS
    if action == "zid.upgrade":
        return role in ZID_UPGRADERS
    return role in REGISTRY_OPERATORS
