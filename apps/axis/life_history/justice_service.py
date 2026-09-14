"""AXIS Justice x Life History - additive module.

Extended case lifecycle + life-history chaining.
Only case EXISTENCE and STATUS go to the chain -
never sensitive case detail.
"""
from __future__ import annotations

from apps.axis.life_history.service import (
    LifeHistoryService,
)

JUSTICE_STAGES = (
    "denuncia",
    "investigacion",
    "audiencia",
    "sentencia",
    "apelacion",
    "cerrado",
)


class JusticeLifeService:
    """Judicial cases chained to life history."""

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

    def open_case(
        self,
        *,
        case_id: str,
        client_account: str,
        lawyer_account: str,
        detail: str,
        stage: str = "denuncia",
    ) -> dict[str, object]:
        if stage not in JUSTICE_STAGES:
            raise ValueError(
                f"stage must be one of"
                f" {JUSTICE_STAGES}"
            )
        store_case = self._store.add_legal_case(
            case_id=case_id,
            client_account=client_account,
            lawyer_account=lawyer_account,
            status="proceso",
            detail=f"[{stage}] {detail}",
            sealed_doc=None,
        )
        person_id = self._person_for_account(
            client_account
        )
        chained = False
        if person_id is not None:
            try:
                self._life._store.add_life_event(
                    person_id,
                    actor=lawyer_account,
                    event_type="justice_case",
                    detail=(
                        f"{case_id} open"
                        f" [{stage}]"
                    ),
                )
                chained = True
            except Exception:
                chained = False
        return {
            **store_case,
            "stage": stage,
            "life_chained": chained,
            "person_id": person_id,
        }

    def advance_case(
        self,
        *,
        case_id: str,
        lawyer_account: str,
        to_stage: str,
        note: str,
    ) -> dict[str, object]:
        if to_stage not in JUSTICE_STAGES:
            raise ValueError(
                f"to_stage must be one of"
                f" {JUSTICE_STAGES}"
            )
        current = self._store.get_case(case_id)
        detail = str(current["detail"])
        closed = to_stage == "cerrado"
        updated = self._store.update_case_status(
            case_id=case_id,
            status=(
                "cerrado" if closed else "proceso"
            ),
            detail=f"[{to_stage}] {note}",
            sealed_doc=None,
        )
        person_id = self._person_for_account(
            str(current["client_account"])
        )
        chained = False
        if person_id is not None:
            try:
                self._life._store.add_life_event(
                    person_id,
                    actor=lawyer_account,
                    event_type=(
                        "justice_status"
                    ),
                    detail=(
                        f"{case_id} ->"
                        f" {to_stage}"
                    ),
                )
                chained = True
            except Exception:
                chained = False
        return {
            **updated,
            "stage": to_stage,
            "previous_stage": detail,
            "life_chained": chained,
            "person_id": person_id,
        }

    def case_expediente(
        self, case_id: str,
    ) -> dict[str, object]:
        case = self._store.get_case(case_id)
        person_id = self._person_for_account(
            str(case["client_account"])
        )
        life_view = None
        if person_id is not None:
            person = (
                self._life._store.get_person(
                    person_id
                )
            )
            life_view = {
                "person_id": person_id,
                "full_name": person[
                    "full_name"
                ],
                "events": len(
                    self._life._store.events_of(
                        person_id
                    )
                ),
                "chain_verified": (
                    self._life._store
                    .events_verify(person_id)
                ),
            }
        return {
            "case": case,
            "life": life_view,
        }
