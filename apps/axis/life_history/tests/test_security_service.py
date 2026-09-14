"""Security x Life History E2E tests."""
from __future__ import annotations

import unittest

from apps.axis.infrastructure.persistence.axis_store import (
    AxisStore,
)
from apps.axis.life_history.security_service import (
    SecurityLifeService,
)
from apps.axis.life_history.service import (
    LifeHistoryService,
)
from apps.axis.life_history.store import (
    LifeHistoryStore,
)

_SUBJECT = "ZID-subject-0001"
_MOTHER = "ZID-mother-s"


class _FakeNetwork:
    def get(self, path):
        zid = path.rsplit("/", 1)[-1]
        if zid in (_SUBJECT, _MOTHER):
            return (
                True,
                {"status": "ACTIVE"},
                None,
            )
        return (False, None, "unknown identity")

    def post(self, path, payload):
        if path == "/documents/seal":
            return (
                True,
                {"document_id": "DOC-s1"},
                None,
            )
        if path == "/history/append":
            return (
                True,
                {"appended": True},
                None,
            )
        return (False, None, "unknown")


class SecurityLifeE2E(unittest.TestCase):
    def _boot(self):
        from shared_engines.common.clocks import (
            SystemClock,
        )
        from shared_engines.storage.database import (
            SQLiteAdapter,
        )

        db = SQLiteAdapter(":memory:")
        clock = SystemClock()
        life = LifeHistoryService(
            store=LifeHistoryStore(db, clock),
            client=_FakeNetwork(),
        )
        birth = life.register_birth_with_network(
            registrar_account="AX-reg-1",
            child_name="Sujeto Nacido",
            birth_date="1990-06-01",
            birth_place="Soyapango",
            sex="M",
            mother_name="Madre S",
            mother_zid=_MOTHER,
        )
        person_id = str(birth["person_id"])
        life.attach_zid_with_audit(
            person_id,
            zid=_SUBJECT,
            actor="biometric-enroll",
        )
        store = AxisStore(db, clock)
        store.add_account(
            account_id="AX-pol-s",
            zid=None,
            name="Agente S",
            role="policia",
        )
        store.add_account(
            account_id="AX-subj-s",
            zid=_SUBJECT,
            name="Sujeto Nacido",
            role="paciente",
        )
        security = SecurityLifeService(
            store=store, life=life
        )
        return store, life, security, person_id

    def test_incident_lifecycle_chained(self):
        store, life, security, person_id = (
            self._boot()
        )
        reported = security.report_incident(
            incident_id="INC-s1",
            police_account="AX-pol-s",
            description="robo reportado",
            subject_account="AX-subj-s",
        )
        self.assertTrue(reported["life_chained"])
        advanced = security.advance_incident(
            incident_id="INC-s1",
            police_account="AX-pol-s",
            to_stage="resuelto",
            note="recuperado",
        )
        self.assertTrue(advanced["life_chained"])
        status = security.incident_status("INC-s1")
        self.assertEqual("resuelto", status["stage"])
        events = life._store.events_of(person_id)
        sec = [
            e["event_type"]
            for e in events
            if e["event_type"].startswith(
                "security"
            )
        ]
        self.assertEqual(
            ["security_incident", "security_status"],
            sec,
        )
        self.assertTrue(
            life._store.events_verify(person_id)
        )

    def test_custody_chain(self):
        store, life, security, _pid = self._boot()
        security.report_incident(
            incident_id="INC-s2",
            police_account="AX-pol-s",
            description="evidencia",
        )
        c1 = security.add_custody(
            incident_id="INC-s2",
            actor_zid="ZID-pol-1",
            action="recolectada",
        )
        self.assertTrue(c1["chain_valid"])
        c2 = security.add_custody(
            incident_id="INC-s2",
            actor_zid="ZID-pol-1",
            action="a fiscalia",
            document_id="DOC-s1",
        )
        self.assertTrue(c2["chain_valid"])
        status = security.incident_status("INC-s2")
        self.assertTrue(status["custody_verified"])

    def test_invalid_stage_rejected(self):
        store, life, security, _pid = self._boot()
        security.report_incident(
            incident_id="INC-s3",
            police_account="AX-pol-s",
            description="x",
        )
        with self.assertRaises(ValueError):
            security.advance_incident(
                incident_id="INC-s3",
                police_account="AX-pol-s",
                to_stage="desaparecido",
                note="x",
            )

    def test_unlinked_subject_degrades(self):
        store, life, security, _pid = self._boot()
        reported = security.report_incident(
            incident_id="INC-s4",
            police_account="AX-pol-s",
            description="sin sujeto",
        )
        self.assertFalse(reported["life_chained"])
        self.assertIsNone(
            reported["subject_person_id"]
        )


if __name__ == "__main__":
    unittest.main(verbosity=2)
