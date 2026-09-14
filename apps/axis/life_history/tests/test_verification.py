"""Third-party verification tests."""
from __future__ import annotations

import unittest

from apps.axis.life_history.repository import (
    LifeHistoryRepository,
)
from apps.axis.life_history.store import (
    LifeHistoryStore,
)
from apps.axis.life_history.verification import (
    person_history_summary,
    verify_birth,
)


class VerificationTests(unittest.TestCase):
    def _store(self):
        from shared_engines.common.clocks import (
            SystemClock,
        )
        from shared_engines.storage.database import (
            SQLiteAdapter,
        )

        db = SQLiteAdapter(":memory:")
        return LifeHistoryStore(
            db, SystemClock()
        )

    def test_verify_birth_valid(self) -> None:
        store = self._store()
        birth = store.register_birth(
            registrar_account="AX-reg-1",
            child_name="Bebe",
            birth_date="2025-01-15",
            birth_place="San Salvador",
            sex="F",
            mother_name="Maria",
            mother_zid="ZID-mother-1",
        )
        report = verify_birth(
            store,
            str(birth["birth_id"]),
            claimed_cert_hash=str(
                birth["cert_hash"]
            ),
        )
        self.assertTrue(report["valid"])
        self.assertTrue(
            report["chain_verified"]
        )

    def test_verify_birth_wrong_hash(self) -> None:
        store = self._store()
        birth = store.register_birth(
            registrar_account="AX-reg-1",
            child_name="Bebe",
            birth_date="2025-01-15",
            birth_place="San Salvador",
            sex="F",
            mother_name="Maria",
            mother_zid="ZID-mother-1",
        )
        report = verify_birth(
            store,
            str(birth["birth_id"]),
            claimed_cert_hash="0" * 64,
        )
        self.assertFalse(report["valid"])

    def test_repository_queries(self) -> None:
        store = self._store()
        store.register_birth(
            registrar_account="AX-reg-1",
            child_name="Uno",
            birth_date="2025-01-01",
            birth_place="A",
            sex="M",
            mother_name="M1",
            mother_zid="ZID-m1",
        )
        store.register_birth(
            registrar_account="AX-reg-1",
            child_name="Dos",
            birth_date="2025-02-01",
            birth_place="B",
            sex="F",
            mother_name="M2",
            mother_zid="ZID-m2",
        )
        repo = LifeHistoryRepository(store)
        self.assertEqual(2, repo.registry_size())
        found = repo.births_between(
            date_from="2025-01-01",
            date_to="2025-01-31",
        )
        self.assertEqual(1, len(found))
        unbound = repo.unbound_persons()
        self.assertEqual(2, len(unbound))


if __name__ == "__main__":
    unittest.main(verbosity=2)
