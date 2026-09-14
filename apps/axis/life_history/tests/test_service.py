"""Life History service tests."""
from __future__ import annotations

import unittest

from apps.axis.life_history.service import (
    LifeHistoryService,
)
from apps.axis.life_history.store import (
    LifeHistoryStore,
    LifeHistoryError,
)

_MOTHER = "ZID-mother-0001"
_FATHER = "ZID-father-0001"


class _FakeNetwork:
    def __init__(self, reachable=True):
        self.reachable = reachable
        self.known = {
            _MOTHER: {"status": "ACTIVE"},
            _FATHER: {"status": "ACTIVE"},
        }
        self.sealed = []

    def get(self, path):
        if not self.reachable:
            return (False, None, "offline")
        zid = path.rsplit("/", 1)[-1]
        if zid in self.known:
            return (
                True,
                dict(self.known[zid]),
                None,
            )
        return (
            False,
            None,
            "unknown identity",
        )

    def post(self, path, payload):
        if not self.reachable:
            return (False, None, "offline")
        if path == "/documents/seal":
            self.sealed.append(dict(payload))
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


class ServiceTests(unittest.TestCase):
    def _svc(self, reachable=True):
        from shared_engines.common.clocks import (
            SystemClock,
        )
        from shared_engines.storage.database import (
            SQLiteAdapter,
        )

        db = SQLiteAdapter(":memory:")
        store = LifeHistoryStore(
            db, SystemClock()
        )
        net = _FakeNetwork(
            reachable=reachable
        )
        svc = LifeHistoryService(
            store=store,
            client=net,
        )
        return svc, net, store

    def _birth(self, svc):
        return (
            svc.register_birth_with_network(
                registrar_account="AX-reg-1",
                child_name="Bebe",
                birth_date="2025-01-15",
                birth_place="San Salvador",
                sex="F",
                mother_name="Maria",
                mother_zid=_MOTHER,
                father_name="Jose",
                father_zid=_FATHER,
            )
        )

    def test_full_birth_sealed(self):
        svc, net, store = self._svc()
        birth = self._birth(svc)
        self.assertTrue(birth["network_ok"])
        self.assertEqual(
            "DOC-1",
            birth["network_seal"],
        )
        self.assertEqual(1, len(net.sealed))
        ok, _n = store.births_chain_verify()
        self.assertTrue(ok)

    def test_offline_birth_survives(self):
        svc, _net, store = self._svc(
            reachable=False
        )
        birth = self._birth(svc)
        self.assertFalse(birth["network_ok"])
        ok, _n = store.births_chain_verify()
        self.assertTrue(ok)
        pending = (
            svc.pending_network_seals()
        )
        self.assertEqual(1, len(pending))

    def test_ghost_parent_rejected(self):
        svc, _net, _store = self._svc()
        try:
            svc.register_birth_with_network(
                registrar_account="AX-reg-1",
                child_name="Fraude",
                birth_date="2025-01-15",
                birth_place="X",
                sex="M",
                mother_name="Impostora",
                mother_zid="ZID-fantasma",
            )
        except LifeHistoryError:
            pass
        else:
            self.fail("ghost parent accepted")

    def test_inactive_parent_rejected(self):
        svc, _net, _store = self._svc()
        svc._client.known[_MOTHER] = {
            "status": "REGISTERED"
        }
        try:
            self._birth(svc)
        except LifeHistoryError:
            pass
        else:
            self.fail("inactive parent accepted")

    def test_attach_notifies_network(self):
        svc, _net, store = self._svc()
        birth = self._birth(svc)
        person_id = str(birth["person_id"])
        person = svc.attach_zid_with_audit(
            person_id,
            zid="ZID-newborn-1",
            actor="biometric-enroll",
        )
        self.assertEqual(
            "biometric_verified",
            person["status"],
        )
        events = store.events_of(person_id)
        self.assertEqual(
            "zid_biometric_upgrade",
            events[-1]["event_type"],
        )


if __name__ == "__main__":
    unittest.main(verbosity=2)
