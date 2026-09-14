"""Outbox bridge E2E tests."""
from __future__ import annotations

import unittest

from apps.axis.life_history.outbox_bridge import (
    OutboxBridge,
)
from apps.axis.life_history.service import (
    LifeHistoryService,
)
from apps.axis.life_history.store import (
    LifeHistoryStore,
)
from shared_engines.common.clocks import SystemClock
from shared_engines.storage.database import (
    SQLiteAdapter,
)

_MOTHER = "ZID-mother-ob"


class _FakeNet:
    def get(self, path):
        zid = path.rsplit("/", 1)[-1]
        if zid == _MOTHER:
            return True, {"status": "ACTIVE"}, None
        return False, None, "unknown identity"

    def post(self, path, payload):
        if path == "/documents/seal":
            return True, {"document_id": "DOC-ob"}, None
        if path == "/history/append":
            return True, {"appended": True}, None
        return False, None, "unknown"


class _FakeOutbox:
    def __init__(self, working=True):
        self.working = working
        self.enqueued = []

    def enqueue(self, event):
        if not self.working:
            raise RuntimeError("outbox unreachable")
        self.enqueued.append(event)


class OutboxBridgeTests(unittest.TestCase):
    def _boot(self, outbox_ok=True):
        db = SQLiteAdapter(":memory:")
        clock = SystemClock()
        life = LifeHistoryService(
            store=LifeHistoryStore(db, clock),
            client=_FakeNet(),
        )
        birth = life.register_birth_with_network(
            registrar_account="AX-reg-1",
            child_name="Bebe Outbox",
            birth_date="2025-01-15",
            birth_place="San Salvador",
            sex="F",
            mother_name="Madre O",
            mother_zid=_MOTHER,
        )
        life._store.add_life_event(
            life._store._db.query_one(
                "SELECT person_id FROM life_persons"
            )["person_id"],
            actor="AX-doc-1",
            event_type="health_exam",
            detail="EXM-1: sangre",
        )
        outbox = _FakeOutbox(working=outbox_ok)
        bridge = OutboxBridge(
            life=life, outbox=outbox, clock=clock
        )
        return life, bridge, outbox

    def test_events_reach_outbox(self):
        life, bridge, outbox = self._boot()
        result = bridge.sync_pending()
        self.assertEqual(2, result["emitted"])
        self.assertEqual(2, len(outbox.enqueued))
        kinds = [
            e["event_type"]
            for e in outbox.enqueued
        ]
        self.assertIn(
            "life.birth.registered", kinds
        )
        self.assertIn(
            "life.health.event", kinds
        )

    def test_sync_is_idempotent(self):
        life, bridge, outbox = self._boot()
        first = bridge.sync_pending()
        self.assertEqual(2, first["emitted"])
        second = bridge.sync_pending()
        self.assertEqual(0, second["emitted"])
        self.assertEqual(
            2, len(outbox.enqueued)
        )

    def test_outbox_down_no_loss(self):
        life, bridge, outbox = self._boot(
            outbox_ok=False
        )
        first = bridge.sync_pending()
        self.assertEqual(0, first["emitted"])
        outbox.working = True
        second = bridge.sync_pending()
        self.assertEqual(2, second["emitted"])
        self.assertEqual(
            2, len(outbox.enqueued)
        )


if __name__ == "__main__":
    unittest.main(verbosity=2)
