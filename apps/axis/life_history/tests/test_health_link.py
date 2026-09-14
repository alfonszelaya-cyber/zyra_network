"""Health x Life History E2E tests."""
from __future__ import annotations

import unittest

from apps.axis.life_history.health_service import (
    HealthLifeLink,
)
from apps.axis.life_history.reminders import (
    ReminderService,
)
from apps.axis.life_history.service import (
    LifeHistoryService,
)
from apps.axis.life_history.store import (
    LifeHistoryStore,
)

_MOTHER = "ZID-mother-0001"


class _FakeNetwork:
    def get(self, path):
        zid = path.rsplit("/", 1)[-1]
        if zid == _MOTHER:
            return (
                True,
                {"status": "ACTIVE"},
                None,
            )
        return (
            False,
            None,
            "unknown identity",
        )

    def post(self, path, payload):
        if path == "/documents/seal":
            return (
                True,
                {"document_id": "DOC-1"},
                None,
            )
        if path == "/history/append":
            return (
                True,
                {"appended": True},
                None,
            )
        return (False, None, "unknown")


class HealthLifeE2E(unittest.TestCase):
    def _boot(self):
        from shared_engines.common.clocks import (
            SystemClock,
        )
        from shared_engines.storage.database import (
            SQLiteAdapter,
        )

        db = SQLiteAdapter(":memory:")
        clock = SystemClock()
        life_store = LifeHistoryStore(db, clock)
        life = LifeHistoryService(
            store=life_store,
            client=_FakeNetwork(),
        )
        birth = (
            life.register_birth_with_network(
                registrar_account=(
                    "AX-reg-1"
                ),
                child_name="Bebe Link",
                birth_date="2025-01-15",
                birth_place="San Salvador",
                sex="F",
                mother_name="Maria",
                mother_zid=_MOTHER,
            )
        )
        life.attach_zid_with_audit(
            str(birth["person_id"]),
            zid="ZID-newborn-link",
            actor="biometric-enroll",
        )
        return db, clock, life, birth

    def test_full_health_life_chain(self) -> None:
        db, clock, life, birth = self._boot()
        from apps.axis.infrastructure.persistence.axis_store import (
            AxisStore,
        )

        store = AxisStore(db, clock)
        store.add_account(
            account_id="AX-pat-life",
            zid="ZID-newborn-link",
            name="Bebe Link",
            role="paciente",
        )
        store.add_account(
            account_id="AX-doc-life",
            zid=None,
            name="Dr Link",
            role="medico",
        )
        link = HealthLifeLink(
            store=store, life=life
        )
        self.assertTrue(
            link.record_exam(
                exam_id="EXM-link1",
                patient_account="AX-pat-life",
                doctor_account="AX-doc-life",
                exam_type="sangre",
            )
        )
        self.assertTrue(
            link.record_result(
                result_id="RES-link1",
                exam_id="EXM-link1",
                patient_account="AX-pat-life",
                summary="anemia detectada",
                severity="media",
                requires_followup=True,
            )
        )
        self.assertTrue(
            link.record_appointment(
                appointment_id="APT-link1",
                patient_account="AX-pat-life",
                reason="control anemia",
                scheduled_at="lunes 9am",
            )
        )
        view = link.patient_longitudinal(
            "AX-pat-life"
        )
        self.assertTrue(
            view["life_linked"]
        )
        self.assertTrue(
            view["chain_verified"]
        )
        types = [
            e["event_type"]
            for e in view["events"]
        ]
        self.assertEqual(
            [
                "birth_registered",
                "zid_biometric_upgrade",
                "health_exam",
                "health_result",
                "health_appointment",
            ],
            types,
        )

    def test_reminders_idempotent(self) -> None:
        db, clock, life, _birth = self._boot()
        from apps.axis.infrastructure.persistence.axis_store import (
            AxisStore,
        )

        store = AxisStore(db, clock)
        store.add_account(
            account_id="AX-pat-rem",
            zid="ZID-newborn-link",
            name="Bebe Link",
            role="paciente",
        )
        store.add_account(
            account_id="AX-doc-rem",
            zid=None,
            name="Dr Rem",
            role="medico",
        )
        link = HealthLifeLink(
            store=store, life=life
        )
        reminders = ReminderService(
            store=store, link=link
        )
        store.add_exam(
            exam_id="EXM-rem",
            patient_account="AX-pat-rem",
            doctor_account="AX-doc-rem",
            exam_type="vista",
        )
        store.add_exam_result(
            result_id="RES-rem",
            exam_id="EXM-rem",
            summary="miope",
            severity="baja",
            requires_followup=True,
            followup_reason="lentes",
            sealed_doc=None,
        )
        store.create_appointment(
            appointment_id="APT-rem",
            patient_account="AX-pat-rem",
            doctor_account="AX-doc-rem",
            result_id="RES-rem",
            reason="lentes",
            scheduled_at="jueves 2pm",
        )
        due = reminders.due_reminders()
        self.assertEqual(1, len(due))
        self.assertTrue(
            due[0]["life_linked"]
        )
        first = reminders.mark_reminded(
            appointment_id="APT-rem",
            patient_account="AX-pat-rem",
            scheduled_at="jueves 2pm",
        )
        self.assertTrue(first)
        second = reminders.mark_reminded(
            appointment_id="APT-rem",
            patient_account="AX-pat-rem",
            scheduled_at="jueves 2pm",
        )
        self.assertFalse(second)

    def test_unlinked_patient_degrades(
        self,
    ) -> None:
        db, clock, life, _birth = self._boot()
        from apps.axis.infrastructure.persistence.axis_store import (
            AxisStore,
        )

        store = AxisStore(db, clock)
        store.add_account(
            account_id="AX-pat-ext",
            zid=None,
            name="Paciente Externo",
            role="paciente",
        )
        link = HealthLifeLink(
            store=store, life=life
        )
        self.assertFalse(
            link.record_exam(
                exam_id="EXM-ext",
                patient_account=(
                    "AX-pat-ext"
                ),
                doctor_account="AX-doc",
                exam_type="sangre",
            )
        )
        view = link.patient_longitudinal(
            "AX-pat-ext"
        )
        self.assertFalse(
            view["life_linked"]
        )


if __name__ == "__main__":
    unittest.main(verbosity=2)
