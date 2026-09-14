"""Judicial automation E2E tests."""
from __future__ import annotations

import unittest

from apps.axis.life_history.judicial_automation import (
    JudicialAutomation,
    JudicialAutomationError,
)
from apps.axis.life_history.service import (
    LifeHistoryService,
)
from apps.axis.life_history.store import (
    LifeHistoryStore,
)
from shared_engines.common.clocks import SystemClock
from shared_engines.storage.database import SQLiteAdapter

_MOTHER = "ZID-mother-jud"


class _FakeNet:
    def get(self, path):
        zid = path.rsplit("/", 1)[-1]
        if zid in (_MOTHER, "ZID-acused-1"):
            return True, {"status": "ACTIVE"}, None
        return False, None, "unknown identity"

    def post(self, path, payload):
        if path == "/documents/seal":
            return True, {"document_id": "DOC-j"}, None
        if path == "/history/append":
            return True, {"appended": True}, None
        return False, None, "unknown"


class JudicialE2E(unittest.TestCase):
    def _boot(self):
        db = SQLiteAdapter(":memory:")
        clock = SystemClock()
        life = LifeHistoryService(
            store=LifeHistoryStore(db, clock),
            client=_FakeNet(),
        )
        birth = life.register_birth_with_network(
            registrar_account="AX-reg-1",
            child_name="Acusado Nacido",
            birth_date="1990-06-01",
            birth_place="San Salvador",
            sex="M",
            mother_name="Madre J",
            mother_zid=_MOTHER,
        )
        person_id = str(birth["person_id"])
        life.attach_zid_with_audit(
            person_id,
            zid="ZID-acused-1",
            actor="biometric-enroll",
        )
        auto = JudicialAutomation(life=life, db=db)
        return life, auto, person_id

    def test_full_penal_flow(self):
        life, auto, person_id = self._boot()
        case = auto.open_case(
            case_id="JC-pen-1",
            person_id=person_id,
            branch="penal",
            actor="AX-abogado",
            actor_role="abogado",
            detail="robo",
        )
        self.assertEqual("denuncia", case["stage"])
        auto.add_evidence(
            case_id="JC-pen-1",
            actor="AX-fiscal",
            actor_role="gobierno",
            description="camara",
        )
        aud = auto.schedule_audiencia(
            case_id="JC-pen-1",
            actor="AX-juez-penal",
            actor_role="juez_penal",
            scheduled_at="viernes 9am",
        )
        self.assertTrue(
            aud["audiencia_id"].startswith("AUD-")
        )
        auto.sentence(
            case_id="JC-pen-1",
            actor="AX-juez-penal",
            actor_role="juez_penal",
            verdict="condena parcial",
        )
        case = auto.get_case("JC-pen-1")
        self.assertEqual("sentencia", case["stage"])
        auto.close_case(
            case_id="JC-pen-1",
            actor="AX-juez-penal",
        )
        self.assertEqual(
            "cerrado",
            auto.get_case("JC-pen-1")["stage"],
        )
        self.assertTrue(
            life._store.events_verify(person_id)
        )
        types = [
            e["event_type"]
            for e in life._store.events_of(
                person_id
            )
        ]
        self.assertIn("justice_evidence", types)

    def test_penal_requires_evidence(self):
        life, auto, person_id = self._boot()
        auto.open_case(
            case_id="JC-pen-2",
            person_id=person_id,
            branch="penal",
            actor="AX-abogado",
            actor_role="abogado",
            detail="sin pruebas",
        )
        with self.assertRaises(
            JudicialAutomationError
        ):
            auto.schedule_audiencia(
                case_id="JC-pen-2",
                actor="AX-juez",
                actor_role="juez_penal",
                scheduled_at="x",
            )

    def test_wrong_sentencer_rejected(self):
        life, auto, person_id = self._boot()
        auto.open_case(
            case_id="JC-pen-3",
            person_id=person_id,
            branch="penal",
            actor="AX-abogado",
            actor_role="abogado",
            detail="x",
        )
        auto.add_evidence(
            case_id="JC-pen-3",
            actor="AX-fiscal",
            actor_role="gobierno",
            description="prueba",
        )
        with self.assertRaises(
            JudicialAutomationError
        ):
            auto.sentence(
                case_id="JC-pen-3",
                actor="AX-medico",
                actor_role="medico",
                verdict="x",
            )

    def test_civil_no_evidence_needed(self):
        life, auto, person_id = self._boot()
        auto.open_case(
            case_id="JC-civ-1",
            person_id=person_id,
            branch="civil",
            actor="AX-abogado",
            actor_role="abogado",
            detail="deuda",
        )
        aud = auto.schedule_audiencia(
            case_id="JC-civ-1",
            actor="AX-juez-civil",
            actor_role="juez_civil",
            scheduled_at="lunes",
        )
        self.assertTrue(
            aud["audiencia_id"].startswith("AUD-")
        )

    def test_unknown_branch_rejected(self):
        life, auto, person_id = self._boot()
        with self.assertRaises(
            JudicialAutomationError
        ):
            auto.open_case(
                case_id="JC-bad",
                person_id=person_id,
                branch="venganza",
                actor="AX-x",
                actor_role="abogado",
                detail="x",
            )


if __name__ == "__main__":
    unittest.main(verbosity=2)
