"""Surveillance E2E tests."""
from __future__ import annotations

import unittest

from apps.axis.life_history.service import (
    LifeHistoryService,
)
from apps.axis.life_history.store import (
    LifeHistoryStore,
)
from apps.axis.life_history.surveillance import (
    SurveillanceService,
)
from shared_engines.common.clocks import SystemClock
from shared_engines.storage.database import (
    SQLiteAdapter,
)

_MOTHER = "ZID-mother-v"


class _FakeNet:
    def get(self, path):
        zid = path.rsplit("/", 1)[-1]
        if zid in (
            _MOTHER,
            "ZID-vigilado-1",
            "ZID-vigilado-2",
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
                {"document_id": "DOC-s"},
                None,
            )
        if path == "/history/append":
            return (
                True,
                {"appended": True},
                None,
            )
        return False, None, "unknown"


class _FakeProvider:
    match_threshold = 0.80

    def __init__(self):
        self._known = {}

    def enroll(self, zid):
        import hashlib

        digest = hashlib.sha256(
            zid.encode("utf-8")
        ).digest()
        vector = tuple(
            float(b) / 255.0
            for b in digest[:8]
        )
        norm = (
            sum(v * v for v in vector)
            ** 0.5
            or 1.0
        )
        self._known[zid] = tuple(
            v / norm for v in vector
        )

    def get_known_template(self, zid):
        return self._known.get(zid)

    def extract_template(self, image):
        for zid, vector in self._known.items():
            if zid.encode() in image:
                return vector
        return (1.0, 0.0)

    def compare(self, a, b):
        if len(a) != len(b):
            return 0.0
        dot = sum(
            x * y for x, y in zip(a, b)
        )
        na = sum(x * x for x in a) ** 0.5
        nb = sum(x * x for x in b) ** 0.5
        if na == 0.0 or nb == 0.0:
            return 0.0
        return max(
            -1.0,
            min(1.0, dot / (na * nb)),
        )


class SurveillanceE2E(unittest.TestCase):
    def _boot(self):
        db = SQLiteAdapter(":memory:")
        life = LifeHistoryService(
            store=LifeHistoryStore(
                db, SystemClock()
            ),
            client=_FakeNet(),
        )
        return db, life

    def test_match_chains_alert(self):
        db, life = self._boot()
        birth = life.register_birth_with_network(
            registrar_account="AX-reg-1",
            child_name="Persona Vigilada",
            birth_date="1995-01-01",
            birth_place="SS",
            sex="M",
            mother_name="Madre V",
            mother_zid=_MOTHER,
        )
        person_id = str(birth["person_id"])
        life.attach_zid_with_audit(
            person_id,
            zid="ZID-vigilado-1",
            actor="enroll",
        )
        provider = _FakeProvider()
        provider.enroll("ZID-vigilado-1")
        svc = SurveillanceService(
            life=life, provider=provider
        )
        result = svc.identify(
            camera_frame=(
                b"frame-ZID-vigilado-1"
            ),
            operator="AX-cam-1",
        )
        self.assertTrue(result["matched"])
        self.assertEqual(
            "ZID-vigilado-1",
            result["zid"],
        )
        events = life._store.events_of(
            person_id
        )
        self.assertEqual(
            "security_alert",
            events[-1]["event_type"],
        )
        self.assertTrue(
            life._store.events_verify(
                person_id
            )
        )

    def test_unknown_no_chain_write(self):
        db, life = self._boot()
        birth = life.register_birth_with_network(
            registrar_account="AX-reg-1",
            child_name="Otra Persona",
            birth_date="1995-02-02",
            birth_place="SS",
            sex="F",
            mother_name="Madre V2",
            mother_zid=_MOTHER,
        )
        person_id = str(birth["person_id"])
        life.attach_zid_with_audit(
            person_id,
            zid="ZID-vigilado-2",
            actor="enroll",
        )
        provider = _FakeProvider()
        provider.enroll("ZID-vigilado-2")
        svc = SurveillanceService(
            life=life, provider=provider
        )
        result = svc.identify(
            camera_frame=b"frame-xyz",
            operator="AX-cam-1",
        )
        self.assertFalse(result["matched"])
        types = [
            e["event_type"]
            for e in life._store.events_of(
                person_id
            )
        ]
        self.assertNotIn(
            "security_alert", types
        )

    def test_no_templates_no_match(self):
        db, life = self._boot()
        provider = _FakeProvider()
        svc = SurveillanceService(
            life=life, provider=provider
        )
        result = svc.identify(
            camera_frame=b"anything",
            operator="AX-cam-1",
        )
        self.assertFalse(result["matched"])


if __name__ == "__main__":
    unittest.main(verbosity=2)
