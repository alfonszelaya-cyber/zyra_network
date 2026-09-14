"""AXIS Health x Life History - additive module."""
from __future__ import annotations

from apps.axis.life_history.service import (
    LifeHistoryService,
)


class HealthLifeLink:
    def __init__(
        self,
        *,
        store,
        life: LifeHistoryService | None,
    ) -> None:
        self._store = store
        self._life = life

    def _person_for_account(
        self, account_id: str,
    ) -> str | None:
        if self._life is None:
            return None
        try:
            account = self._store.get_account(
                account_id
            )
        except LookupError:
            return None
        zid = account.get("zid")
        if not zid:
            return None
        row = self._life._store._db.query_one(
            "SELECT person_id FROM life_persons"
            " WHERE zid = ?",
            (str(zid),),
        )
        if row is None:
            return None
        return str(row["person_id"])

    def record_exam(
        self,
        *,
        exam_id: str,
        patient_account: str,
        doctor_account: str,
        exam_type: str,
    ) -> bool:
        person_id = self._person_for_account(
            patient_account
        )
        if person_id is None:
            return False
        try:
            self._life._store.add_life_event(
                person_id,
                actor=doctor_account,
                event_type="health_exam",
                detail=f"{exam_id}: {exam_type}",
            )
            return True
        except Exception:
            return False

    def record_result(
        self,
        *,
        result_id: str,
        exam_id: str,
        patient_account: str,
        summary: str,
        severity: str,
        requires_followup: bool,
    ) -> bool:
        person_id = self._person_for_account(
            patient_account
        )
        if person_id is None:
            return False
        try:
            self._life._store.add_life_event(
                person_id,
                actor="axis-health",
                event_type="health_result",
                detail=(
                    f"{result_id}: {summary}"
                    f" [{severity}]"
                ),
            )
            return True
        except Exception:
            return False

    def record_appointment(
        self,
        *,
        appointment_id: str,
        patient_account: str,
        reason: str,
        scheduled_at: str,
    ) -> bool:
        person_id = self._person_for_account(
            patient_account
        )
        if person_id is None:
            return False
        try:
            self._life._store.add_life_event(
                person_id,
                actor="axis-health",
                event_type="health_appointment",
                detail=(
                    f"{appointment_id}:"
                    f" {reason} @ {scheduled_at}"
                ),
            )
            return True
        except Exception:
            return False

    def patient_longitudinal(
        self, account_id: str,
    ) -> dict[str, object]:
        person_id = self._person_for_account(
            account_id
        )
        if person_id is None:
            return {
                "account_id": account_id,
                "life_linked": False,
            }
        person = self._life._store.get_person(
            person_id
        )
        events = self._life._store.events_of(
            person_id
        )
        return {
            "account_id": account_id,
            "life_linked": True,
            "person_id": person_id,
            "full_name": person["full_name"],
            "zid": person["zid"],
            "status": person["status"],
            "events": list(events),
            "chain_verified": (
                self._life._store.events_verify(
                    person_id
                )
            ),
        }
