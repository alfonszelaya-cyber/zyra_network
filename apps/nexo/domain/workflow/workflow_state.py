
"""Workflow State - estados y transiciones (NG7)."""
from __future__ import annotations

WORKFLOW_STATES = ("CREATED", "RUNNING", "PAUSED",
                   "COMPLETED", "CANCELLED",
                   "FAILED")

_TRANSITIONS = {
    "CREATED": ("RUNNING", "CANCELLED"),
    "RUNNING": ("PAUSED", "COMPLETED",
                "CANCELLED", "FAILED"),
    "PAUSED": ("RUNNING", "CANCELLED"),
    "COMPLETED": (),
    "CANCELLED": (),
    "FAILED": (),
}

def assert_transition(current, new) -> None:
    allowed = _TRANSITIONS.get(current, ())
    if new not in allowed:
        raise ValueError(
            "transicion invalida: " + current
            + " -> " + new)
