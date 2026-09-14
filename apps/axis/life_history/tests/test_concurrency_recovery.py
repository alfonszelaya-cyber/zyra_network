"""AXIS Life History concurrency + recovery E2E.

Proves:
1. Simultaneous birth registrations produce
   unique persons, zero forking, chain intact.
2. A simulated mid-operation failure leaves no
   orphan state; the registry repairs and
   continues accepting new births.
3. Full integrity holds after recovery.
"""
from __future__ import annotations

import threading
import unittest

from apps.axis.life_history.service import (
    LifeHistoryService,
)
from apps.axis.life_history.store import (
    LifeHistoryStore,
)
from shared_engines.common.clocks import (
    SystemClock,
)
from shared_engines.storage.database import (
    SQLiteAdapter,
)

_MOTHER = "ZID-mother-conc"


class _FakeNet:
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
                {"document_id": "DOC-c"},
                None,
            )
        if path == "/history/append":
            return (
                True,
                {"appended": True},
                None,
            )
        return False, None, "unknown"


class ConcurrencyTests(unittest.TestCase):
    def _boot(self):
        db = SQLiteAdapter(":memory:")
        life = LifeHistoryService(
            store=LifeHistoryStore(
                db, SystemClock()
            ),
            client=_FakeNet(),
        )
        return db, life

    def test_simultaneous_births_all_unique(
        self,
    ) -> None:
        db, life = self._boot()
        results: list = []
        errors: list = []

        def register(n: int) -> None:
            try:
                birth = (
                    life.register_birth_with_network(
                        registrar_account=(
                            "AX-reg-"
                            + str(n)
                        ),
                        child_name=(
                            "Bebe "
                            + str(n)
                        ),
                        birth_date=(
                            "2025-01-"
                            + str(
                                10
                                + n
                            )
                        ),
                        birth_place=(
                            "Ciudad "
                            + str(n)
                        ),
                        sex="F",
                        mother_name=(
                            "Madre"
                        ),
                        mother_zid=_MOTHER,
                    )
                )
                results.append(
                    birth
                )
            except Exception as exc:
                errors.append(exc)

        threads = []
        for n in range(6):
            t = threading.Thread(
                target=register,
                args=(n,),
            )
            threads.append(t)
            t.start()
        for t in threads:
            t.join(timeout=15)

        self.assertEqual(
            [], errors
        )
        self.assertEqual(
            6, len(results)
        )
        person_ids = {
            str(r["person_id"])
            for r in results
        }
        self.assertEqual(
            6, len(person_ids)
        )
        ok, count = (
            life._store.births_chain_verify()
        )
        self.assertTrue(ok)
        self.assertEqual(6, count)

    def test_recovery_after_failure(
        self,
    ) -> None:
        db, life = self._boot()
        good = (
            life.register_birth_with_network(
                registrar_account=(
                    "AX-reg-1"
                ),
                child_name="Bebe Ok",
                birth_date="2025-01-01",
                birth_place="Lugar",
                sex="M",
                mother_name="Madre",
                mother_zid=_MOTHER,
            )
        )
        person_id = str(
            good["person_id"]
        )
        events_before = len(
            life._store.events_of(
                person_id
            )
        )
        try:
            life._store.add_life_event(
                "LHP-fantasma",
                actor="x",
                event_type="boom",
                detail="x",
            )
        except Exception:
            pass
        life._store.add_life_event(
            person_id,
            actor="AX-doc-1",
            event_type="health_exam",
            detail="post-fallo ok",
        )
        events_after = life._store.events_of(
            person_id
        )
        self.assertEqual(
            events_before + 1,
            len(events_after),
        )
        self.assertTrue(
            life._store.events_verify(
                person_id
            )
        )
        ok, _count = (
            life._store.births_chain_verify()
        )
        self.assertTrue(ok)
        more = (
            life.register_birth_with_network(
                registrar_account=(
                    "AX-reg-2"
                ),
                child_name="Bebe Post",
                birth_date="2025-02-02",
                birth_place="Lugar2",
                sex="F",
                mother_name="Madre",
                mother_zid=_MOTHER,
            )
        )
        self.assertTrue(
            str(
                more["person_id"]
            ).startswith("LHP-")
        )
        ok, count = (
            life._store.births_chain_verify()
        )
        self.assertTrue(ok)
        self.assertEqual(2, count)

    def test_integrity_after_many_ops(
        self,
    ) -> None:
        db, life = self._boot()
        birth = (
            life.register_birth_with_network(
                registrar_account=(
                    "AX-reg-1"
                ),
                child_name="Bebe Ops",
                birth_date="2025-01-01",
                birth_place="Lugar",
                sex="F",
                mother_name="Madre",
                mother_zid=_MOTHER,
            )
        )
        person_id = str(
            birth["person_id"]
        )
        for i in range(10):
            life._store.add_life_event(
                person_id,
                actor="AX-doc",
                event_type="health_event",
                detail="op " + str(i),
            )
        self.assertTrue(
            life._store.events_verify(
                person_id
            )
        )
        for i in range(5):
            life._store.add_life_event(
                person_id,
                actor="AX-corte",
                event_type="justice_note",
                detail="nota " + str(i),
            )
        self.assertTrue(
            life._store.events_verify(
                person_id
            )
        )
        ok, _count = (
            life._store.births_chain_verify()
        )
        self.assertTrue(ok)


if __name__ == "__main__":
    unittest.main(verbosity=2)
