"""AGRO areas persistence + concurrency tests."""
from __future__ import annotations

import threading
import unittest

from apps.agro.infrastructure.persistence.agro_area_store import (
    AgroAreaStore,
)
from shared_engines.common.clocks import FrozenClock
from shared_engines.storage.database import (
    SQLiteAdapter,
)


class AreaPersistenceTests(unittest.TestCase):
    def _store(self):
        db = SQLiteAdapter(":memory:")
        return AgroAreaStore(db, FrozenClock())

    def test_all_six_areas_roundtrip(self):
        store = self._store()
        land = store.add_land(
            producer_id="PRD-1",
            location="Chalatenango",
            size_hectares=12.5,
            land_use="maiz",
        )
        self.assertTrue(
            land["land_id"].startswith("LND-")
        )
        self.assertEqual(
            1,
            len(
                store.lands_of(
                    producer_id="PRD-1"
                )
            ),
        )
        sale = store.create_sale(
            producer_id="PRD-1",
            buyer="Exportador X",
            product="maiz",
            quantity=50,
            unit="quintal",
            price=1000,
        )
        store.complete_sale(
            sale_id=sale["sale_id"]
        )
        sales = store.sales_of(
            producer_id="PRD-1"
        )
        self.assertEqual(
            "completed",
            sales[0]["status"],
        )
        risk = store.report_risk(
            producer_id="PRD-1",
            risk_type="climatico",
            severity="alta",
            detail="sequia",
        )
        self.assertEqual(
            1,
            len(
                store.open_risks(
                    producer_id="PRD-1"
                )
            ),
        )
        store.resolve_risk(
            risk_id=risk["risk_id"]
        )
        self.assertEqual(
            0,
            len(
                store.open_risks(
                    producer_id="PRD-1"
                )
            ),
        )
        store.add_machinery(
            producer_id="PRD-1",
            machine_type="tractor",
            description="2020",
        )
        self.assertEqual(
            1,
            len(
                store.machinery_of(
                    producer_id="PRD-1"
                )
            ),
        )
        store.add_inventory_item(
            producer_id="PRD-1",
            item_name="semillas",
            quantity=100,
            unit="lb",
        )
        self.assertEqual(
            1,
            len(
                store.inventory_of(
                    producer_id="PRD-1"
                )
            ),
        )
        store.add_water_source(
            producer_id="PRD-1",
            source_type="pozo",
            capacity_liters=50000,
        )
        self.assertEqual(
            1,
            len(
                store.water_sources_of(
                    producer_id="PRD-1"
                )
            ),
        )

    def test_concurrent_writes_all_persist(self):
        db = SQLiteAdapter(":memory:")
        store = AgroAreaStore(db, FrozenClock())
        results = []
        errors = []

        def add_land(n):
            try:
                results.append(
                    store.add_land(
                        producer_id="PRD-conc",
                        location="Zona " + str(n),
                        size_hectares=1.0 + n,
                    )
                )
            except Exception as exc:
                errors.append(exc)

        threads = []
        for n in range(8):
            t = threading.Thread(
                target=add_land, args=(n,)
            )
            threads.append(t)
            t.start()
        for t in threads:
            t.join(timeout=15)
        self.assertEqual([], errors)
        self.assertEqual(
            8,
            len(
                store.lands_of(
                    producer_id="PRD-conc"
                )
            ),
        )

    def test_sale_unknown_rejected(self):
        store = self._store()
        with self.assertRaises(LookupError):
            store.complete_sale(
                sale_id="SAL-fantasma"
            )

    def test_risk_unknown_rejected(self):
        store = self._store()
        with self.assertRaises(LookupError):
            store.resolve_risk(
                risk_id="RSK-fantasma"
            )


if __name__ == "__main__":
    unittest.main(verbosity=2)
