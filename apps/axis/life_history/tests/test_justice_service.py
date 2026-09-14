"""Justice x Life History E2E tests."""
from __future__ import annotations

import unittest

from apps.axis.infrastructure.persistence.axis_store import (
    AxisStore,
)
from apps.axis.life_history.justice_service import (
    JusticeLifeService,
)
from apps.axis.life_history.service import (
    LifeHistoryService,
)
from apps.axis.life_history.store import (
    LifeHistoryStore,
)

_CLIENT_ZID = "ZID-client-0001"
_MOTHER_ZID = "ZID-mother-c"


class _FakeNetwork:
    def get(self, path):
        zid = path.rsplit("/", 1)[-1]
        if zid in (
            _CLIENT_ZID,
            _MOTHER_ZID,
        ):
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
                {"document_id": "DOC-j1"},
                None,
            )
        if path == "/history/append":
            return (
                True,
                {"appended": True},
                None,
            )
        return (False, None, "unknown")


class JusticeLifeE2E(unittest.TestCase):
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
                child_name="Cliente Nacido",
                birth_date="1995-03-10",
                birth_place="San Salvador",
                sex="M",
                mother_name="Madre C",
                mother_zid=_MOTHER_ZID,
            )
        )
        person_id = str(birth["person_id"])
        life.attach_zid_with_audit(
            person_id,
            zid=_CLIENT_ZID,
            actor="biometric-enroll",
        )
        store = AxisStore(db, clock)
        store.add_account(
            account_id="AX-cli-j",
            zid=_CLIENT_ZID,
            name="Cliente Nacido",
            role="paciente",
        )
        store.add_account(
            account_id="AX-law-j",
            zid=None,
            name="Abogado J",
            role="abogado",
        )
        justice = JusticeLifeService(
            store=store, life=life
        )
        return (
            store,
            life,
            justice,
            person_id,
        )

    def test_case_lifecycle_chained(
        self,
    ) -> None:
        store, life, justice, person_id = (
            self._boot()
        )
        opened = justice.open_case(
            case_id="CASE-j1",
            client_account="AX-cli-j",
            lawyer_account="AX-law-j",
            detail="robo con violencia",
            stage="denuncia",
        )
        self.assertTrue(
            opened["life_chained"]
        )
        advanced = justice.advance_case(
            case_id="CASE-j1",
            lawyer_account="AX-law-j",
            to_stage="sentencia",
            note="condena parcial",
        )
        self.assertTrue(
            advanced["life_chained"]
        )
        closed = justice.advance_case(
            case_id="CASE-j1",
            lawyer_account="AX-law-j",
            to_stage="cerrado",
            note="cumplida",
        )
        self.assertEqual(
            "cerrado",
            closed["stage"],
        )
        self.assertEqual(
            "cerrado",
            closed["status"],
        )
        events = life._store.events_of(
            person_id
        )
        justice_events = [
            e["event_type"]
            for e in events
            if e["event_type"].startswith(
                "justice"
            )
        ]
        self.assertEqual(
            [
                "justice_case",
                "justice_status",
                "justice_status",
            ],
            justice_events,
        )
        self.assertTrue(
            life._store.events_verify(
                person_id
            )
        )

    def test_invalid_stage_rejected(
        self,
    ) -> None:
        store, life, justice, _pid = (
            self._boot()
        )
        with self.assertRaises(ValueError):
            justice.open_case(
                case_id="CASE-bad",
                client_account="AX-cli-j",
                lawyer_account="AX-law-j",
                detail="x",
                stage="venganza",
            )

    def test_expediente_with_life_view(
        self,
    ) -> None:
        store, life, justice, person_id = (
            self._boot()
        )
        justice.open_case(
            case_id="CASE-j2",
            client_account="AX-cli-j",
            lawyer_account="AX-law-j",
            detail="estafa",
            stage="investigacion",
        )
        file = justice.case_expediente(
            "CASE-j2"
        )
        self.assertEqual(
            "CASE-j2",
            file["case"]["case_id"],
        )
        self.assertIsNotNone(
            file["life"]
        )
        self.assertTrue(
            file["life"][
                "chain_verified"
            ]
        )

    def test_unlinked_client_degrades(
        self,
    ) -> None:
        store, life, justice, _pid = (
            self._boot()
        )
        store.add_account(
            account_id="AX-cli-ext",
            zid=None,
            name="Cliente Externo",
            role="paciente",
        )
        opened = justice.open_case(
            case_id="CASE-ext",
            client_account="AX-cli-ext",
            lawyer_account="AX-law-j",
            detail="x",
            stage="denuncia",
        )
        self.assertFalse(
            opened["life_chained"]
        )
        self.assertIsNone(
            opened["person_id"]
        )


if __name__ == "__main__":
    unittest.main(verbosity=2)
