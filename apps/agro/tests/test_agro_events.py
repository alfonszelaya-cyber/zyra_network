"""AGRO events E2E tests."""
from __future__ import annotations

import unittest
import uuid

from apps.agro.services.agro_events import (
    AgroEventService,
)
from apps.agro.infrastructure.persistence.agro_store import (
    AgroStore,
)
from shared_engines.common.clocks import FrozenClock
from shared_engines.storage.database import SQLiteAdapter


class _FakeLink:
    def __init__(self, working=True):
        self.working = working
        self.calls = []
        self._seq = 100

    def record_agro_event(self, zid, event, detail):
        self.calls.append((zid, event, detail))
        if not self.working:
            return (False, None, "network down")
        self._seq += 1
        return (True, {"seq": self._seq}, None)


class AgroEventsE2E(unittest.TestCase):
    def _boot(self, has_zid=True, link_ok=True):
        db = SQLiteAdapter(":memory:")
        clock = FrozenClock()
        store = AgroStore(db, clock)
        producer_id = (
            "PRD-" + uuid.uuid4().hex[:10]
        )
        store.add_producer(
            producer_id=producer_id,
            zid=(
                "ZID-agro-1"
                if has_zid
                else None
            ),
            name="Jose Rural",
            role="agricultor",
            synced=has_zid,
            producer_type="agricultor",
            location="Chalatenango",
        )
        link = _FakeLink(working=link_ok)
        svc = AgroEventService(
            store=store, link=link
        )
        return svc, link, producer_id

    def test_producer_events_with_zid(self):
        svc, link, producer_id = self._boot()
        seq1 = svc.producer_registered(
            producer_id=producer_id,
            producer_type="agricultor",
        )
        self.assertIsNotNone(seq1)
        seq2 = svc.producer_verified(
            producer_id=producer_id
        )
        self.assertIsNotNone(seq2)
        self.assertEqual(2, len(link.calls))
        self.assertEqual(
            "ZID-agro-1",
            link.calls[0][0],
        )
        self.assertEqual(
            "producer.registered",
            link.calls[0][1],
        )

    def test_production_and_sale_events(self):
        svc, link, producer_id = self._boot()
        seq1 = svc.production_registered(
            producer_id=producer_id,
            product="maiz",
            quantity=50,
            unit="quintal",
        )
        seq2 = svc.sale_created(
            producer_id=producer_id,
            sale_id="SALE-1",
            detail="50 qq exportacion",
        )
        seq3 = svc.sale_completed(
            producer_id=producer_id,
            sale_id="SALE-1",
        )
        self.assertIsNotNone(seq1)
        self.assertIsNotNone(seq2)
        self.assertIsNotNone(seq3)
        self.assertEqual(3, len(link.calls))

    def test_aid_risk_asset_events(self):
        svc, link, producer_id = self._boot()
        svc.aid_transition(
            producer_id=producer_id,
            aid_id="AID-1",
            transition="AID_REQUESTED",
        )
        svc.aid_transition(
            producer_id=producer_id,
            aid_id="AID-1",
            transition="AID_DELIVERED",
        )
        svc.risk_detected(
            producer_id=producer_id,
            risk_type="climatico",
            detail="sequia",
        )
        svc.incident_created(
            producer_id=producer_id,
            incident_id="INC-1",
            detail="plaga",
        )
        svc.asset_registered(
            producer_id=producer_id,
            asset_type="maquinaria",
            detail="tractor",
        )
        self.assertEqual(5, len(link.calls))
        kinds = [c[1] for c in link.calls]
        self.assertIn("aid.requested", kinds)
        self.assertIn("aid.delivered", kinds)
        self.assertIn("risk.detected", kinds)
        self.assertIn(
            "incident.created", kinds
        )
        self.assertIn(
            "asset.registered", kinds
        )

    def test_no_zid_returns_none(self):
        svc, link, producer_id = self._boot(
            has_zid=False
        )
        seq = svc.producer_registered(
            producer_id=producer_id,
            producer_type="agricultor",
        )
        self.assertIsNone(seq)
        self.assertEqual(0, len(link.calls))

    def test_network_down_never_raises(self):
        svc, link, producer_id = self._boot(
            link_ok=False
        )
        seq = svc.production_registered(
            producer_id=producer_id,
            product="frijol",
            quantity=10,
            unit="quintal",
        )
        self.assertIsNone(seq)


if __name__ == "__main__":
    unittest.main(verbosity=2)
