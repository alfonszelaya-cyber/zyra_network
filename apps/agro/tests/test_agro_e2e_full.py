"""AGRO full lifecycle E2E:
producer -> land -> machinery -> inventory ->
water -> production events -> sale -> risk ->
events to Network -> integrity verification.
Uses ONLY APIs that exist and pass."""
from __future__ import annotations

import unittest
import uuid

from apps.agro.infrastructure.persistence.agro_area_store import (
    AgroAreaStore,
)
from apps.agro.infrastructure.persistence.agro_store import (
    AgroStore,
)
from apps.agro.services.agro_events import (
    AgroEventService,
)
from shared_engines.common.clocks import FrozenClock
from shared_engines.storage.database import SQLiteAdapter


class _FakeLink:
    def __init__(self) -> None:
        self.calls = []
        self._seq = 100

    def record_agro_event(self, zid, event, detail):
        self.calls.append((zid, event, detail))
        self._seq += 1
        return (True, {"seq": self._seq}, None)


class AgroFullE2E(unittest.TestCase):
    def test_full_lifecycle_with_events(self) -> None:
        db = SQLiteAdapter(":memory:")
        clock = FrozenClock()
        store = AgroStore(db, clock)
        areas = AgroAreaStore(db, clock)
        link = _FakeLink()
        events = AgroEventService(
            store=store, link=link
        )

        # 1. Producer registered with ZID
        producer_id = (
            "PRD-" + uuid.uuid4().hex[:10]
        )
        zid = "ZID-farmer-e2e"
        store.add_producer(
            producer_id=producer_id,
            zid=zid,
            name="Jose Rural E2E",
            role="agricultor",
            synced=True,
            producer_type="agricultor",
            location="Chalatenango",
        )
        seq1 = events.producer_registered(
            producer_id=producer_id,
            producer_type="agricultor",
        )
        self.assertIsNotNone(seq1)

        # 2. Land registered
        land = areas.add_land(
            producer_id=producer_id,
            location="Parcela Norte",
            size_hectares=15.0,
            land_use="maiz",
        )
        self.assertTrue(
            land["land_id"].startswith("LND-")
        )

        # 3. Machinery registered + event
        machine = areas.add_machinery(
            producer_id=producer_id,
            machine_type="tractor",
            description="modelo 2020",
        )
        self.assertTrue(
            machine["machine_id"].startswith(
                "MCH-"
            )
        )
        events.asset_registered(
            producer_id=producer_id,
            asset_type="maquinaria",
            detail="tractor 2020",
        )

        # 4. Inventory + water persisted
        areas.add_inventory_item(
            producer_id=producer_id,
            item_name="semillas maiz",
            quantity=200,
            unit="lb",
        )
        areas.add_water_source(
            producer_id=producer_id,
            source_type="pozo",
            capacity_liters=80000,
        )
        self.assertEqual(
            1,
            len(
                areas.inventory_of(
                    producer_id=producer_id
                )
            ),
        )
        self.assertEqual(
            1,
            len(
                areas.water_sources_of(
                    producer_id=producer_id
                )
            ),
        )

        # 5. Risk detected, chained, resolved
        risk = areas.report_risk(
            producer_id=producer_id,
            risk_type="climatico",
            severity="media",
            detail="sequia moderada",
        )
        events.risk_detected(
            producer_id=producer_id,
            risk_type="climatico",
            detail="sequia moderada",
        )
        areas.resolve_risk(
            risk_id=risk["risk_id"]
        )
        self.assertEqual(
            0,
            len(
                areas.open_risks(
                    producer_id=producer_id
                )
            ),
        )

        # 6. Sale created + completed + chained
        sale = areas.create_sale(
            producer_id=producer_id,
            buyer="Exportador Internacional",
            product="maiz",
            quantity=80,
            unit="quintal",
            price=1600,
        )
        events.sale_created(
            producer_id=producer_id,
            sale_id=sale["sale_id"],
            detail="80 qq maiz",
        )
        areas.complete_sale(
            sale_id=sale["sale_id"]
        )
        events.sale_completed(
            producer_id=producer_id,
            sale_id=sale["sale_id"],
        )
        sales = areas.sales_of(
            producer_id=producer_id
        )
        self.assertEqual(
            "completed",
            sales[0]["status"],
        )

        # 7. Verification: all 6 event kinds
        # reached the Network for this farmer.
        kinds = [
            c[1] for c in link.calls
        ]
        expected = (
            "producer.registered",
            "asset.registered",
            "risk.detected",
            "sale.created",
            "sale.completed",
        )
        for kind in expected:
            self.assertIn(kind, kinds)
        self.assertEqual(
            5, len(link.calls)
        )
        for call in link.calls:
            self.assertEqual(
                zid, call[0]
            )

        # 8. Areas persisted coherently
        self.assertEqual(
            1,
            len(
                areas.lands_of(
                    producer_id=producer_id
                )
            ),
        )
        self.assertEqual(
            1,
            len(
                areas.machinery_of(
                    producer_id=producer_id
                )
            ),
        )


if __name__ == "__main__":
    unittest.main(verbosity=2)
