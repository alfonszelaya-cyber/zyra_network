
"""Contratos de eventos SEMILLA_* (SM6)."""
from __future__ import annotations
import uuid

SOURCE = "semilla"
EVENT_VERSION = "1.0"

SEMILLA_STUDENT_REGISTERED = "SEMILLA_STUDENT_REGISTERED"
SEMILLA_ENROLLED = "SEMILLA_ENROLLED"
SEMILLA_ATTENDANCE_LOW = "SEMILLA_ATTENDANCE_LOW"
SEMILLA_TALENT_DETECTED = "SEMILLA_TALENT_DETECTED"
SEMILLA_SCHOLARSHIP_APPROVED = "SEMILLA_SCHOLARSHIP_APPROVED"
SEMILLA_GRADE_POSTED = "SEMILLA_GRADE_POSTED"
SEMILLA_PERIOD_ADVANCED = "SEMILLA_PERIOD_ADVANCED"
SEMILLA_CERTIFIED = "SEMILLA_CERTIFIED"
SEMILLA_DROPOUT_RISK = "SEMILLA_DROPOUT_RISK"

SEMILLA_EVENTS = (
    SEMILLA_STUDENT_REGISTERED, SEMILLA_ENROLLED,
    SEMILLA_ATTENDANCE_LOW,
    SEMILLA_TALENT_DETECTED,
    SEMILLA_SCHOLARSHIP_APPROVED,
    SEMILLA_GRADE_POSTED,
    SEMILLA_PERIOD_ADVANCED,
    SEMILLA_CERTIFIED, SEMILLA_DROPOUT_RISK)

def is_valid_event(name) -> bool:
    return name in SEMILLA_EVENTS

def make_event(name, student_id="",
               payload=None,
               occurred_at=None) -> dict:
    if not is_valid_event(name):
        raise ValueError("evento no catalogado: "
                         + str(name))
    return {"event_id": "SMSEVT-"
            + str(uuid.uuid4()),
            "event": name, "source": SOURCE,
            "version": EVENT_VERSION,
            "student_id": str(student_id),
            "payload": dict(payload or {}),
            "occurred_at": occurred_at}
