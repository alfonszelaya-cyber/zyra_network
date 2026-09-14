"""AXIS Health reminders - additive module."""
from __future__ import annotations

from apps.axis.life_history.health_service import (
    HealthLifeLink,
)


class ReminderService:
    def __init__(
        self,
        *,
        store,
        link: HealthLifeLink,
    ) -> None:
        self._store = store
        self._link = link
        self._marked: set[str] = set()

    def due_reminders(
        self,
    ) -> list[dict[str, object]]:
        pending = self._store.pending_reminders()
        out: list[dict[str, object]] = []
        for item in pending:
            out.append(
                {
                    "appointment_id": item[
                        "appointment_id"
                    ],
                    "patient_account": item[
                        "patient_account"
                    ],
                    "reason": item["reason"],
                    "scheduled_at": item[
                        "scheduled_at"
                    ],
                    "life_linked": (
                        self._link
                        ._person_for_account(
                            item[
                                "patient_account"
                            ]
                        )
                        is not None
                    ),
                }
            )
        return out

    def mark_reminded(
        self,
        *,
        appointment_id: str,
        patient_account: str,
        scheduled_at: str,
    ) -> bool:
        if appointment_id in self._marked:
            return False
        self._marked.add(appointment_id)
        return self._link.record_appointment(
            appointment_id=appointment_id,
            patient_account=patient_account,
            reason="reminder_sent",
            scheduled_at=scheduled_at,
        )
