"""SUBASTAS commerce e2e ADD-ONLY - canonical app
registration (like MPE), trust, winner persisted,
order, payment, commission, settlement, shipment,
tracking, delivery, mutual reputation on network,
history by ZID, direct purchase, radar VIP,
offline resilience."""
from __future__ import annotations

import json
import socket
import threading
from pathlib import Path
from urllib.request import Request, urlopen

socket.setdefaulttimeout(20)

from shared_engines.common.clocks import FrozenClock
from shared_engines.runtime.capabilities import ZyraCapabilities
from shared_engines.runtime.combined_api import serve_combined
from shared_engines.runtime.config import RuntimeConfig
from shared_engines.runtime.kernel import ZyraKernel
from shared_engines.storage.database import SQLiteAdapter
from shared_engines.verification.signatures import Ed25519Signer

from apps.subastas.infrastructure.network.network_client import NetworkClient
from apps.subastas.infrastructure.persistence.subastas_store import SubastasStore
from apps.subastas.server import serve_subastas


class _Eco:
    def __init__(self, tmp_path: Path) -> None:
        self.net_db = SQLiteAdapter(tmp_path / "network.db")
        signer, _ = Ed25519Signer.generate()
        self.kernel = ZyraKernel(
            db=self.net_db,
            clock=FrozenClock(),
            signer=signer,
            config=RuntimeConfig(host="127.0.0.1", port=0, api_token=None),
        )
        self.kernel.bootstrap_root()
        self.caps = ZyraCapabilities(
            self.net_db,
            FrozenClock(),
            identity=self.kernel.identity,
            signer=signer,
        )
        self.net_server = serve_combined(
            self.kernel, self.caps, host="127.0.0.1", port=0
        )
        threading.Thread(
            target=self.net_server.serve_forever, daemon=True
        ).start()
        self.net_base = (
            "http://127.0.0.1:"
            f"{self.net_server.server_address[1]}"
        )
        self.client = NetworkClient(self.net_base, max_retries=1)
        self.sbs_db = SQLiteAdapter(tmp_path / "sbs.db")
        self.store = SubastasStore(self.sbs_db, FrozenClock())
        self.sbs_server = serve_subastas(self.store, self.client)
        threading.Thread(
            target=self.sbs_server.serve_forever, daemon=True
        ).start()
        self.sbs_base = (
            "http://127.0.0.1:"
            f"{self.sbs_server.bound_port}"
        )

    def register_app_canonical(self) -> None:
        ok, data, err = self.client.post(
            "/apps/register",
            {
                "app_id": "subastas",
                "display_name": "SUBASTAS",
                "scopes": ["display_name", "contact"],
            },
        )
        assert ok is True, (
            "apps/register failed: "
            + json.dumps({"data": data, "error": err})
        )

    def close(self) -> None:
        self.sbs_server.shutdown()
        self.sbs_server.server_close()
        self.net_server.shutdown()
        self.net_server.server_close()
        self.sbs_db.close()
        self.net_db.close()


def _pf(url: str, doc: dict) -> str:
    request = Request(
        url,
        data=(
            "&".join(str(k) + "=" + str(v) for k, v in doc.items())
        ).encode("utf-8"),
        method="POST",
    )
    with urlopen(request, timeout=15) as r:
        return r.read().decode("utf-8")


def _pj(url: str, doc: dict) -> dict:
    request = Request(
        url,
        data=json.dumps(doc).encode("utf-8"),
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    with urlopen(request, timeout=15) as r:
        body = json.loads(r.read().decode("utf-8"))
    assert isinstance(body, dict)
    return body


def _gj(url: str) -> dict:
    with urlopen(url, timeout=15) as r:
        body = json.loads(r.read().decode("utf-8"))
    assert isinstance(body, dict)
    return body


def _h(url: str) -> str:
    with urlopen(url, timeout=15) as r:
        return r.read().decode("utf-8")


def _accounts(eco) -> None:
    eco.store.add_account(
        account_id="SBS-seller01", zid=None, name="Vendedor Uno"
    )
    eco.store.add_account(
        account_id="SBS-buyer001", zid=None, name="Comprador Uno"
    )


def test_1_auction_full_commerce(tmp_path: Path) -> None:
    eco = _Eco(tmp_path)
    try:
        eco.register_app_canonical()
        _accounts(eco)
        listing_html = _pf(
            eco.sbs_base + "/subastas/listing",
            {
                "seller_account": "SBS-seller01",
                "title": "Moto usada 2019",
                "description": "buena",
                "base_price": 500,
            },
        )
        assert "SELLADO" in listing_html
        listing_id = eco.store.list_open()[0]["listing_id"]
        body = _pj(
            eco.sbs_base + "/subastas/api/bids",
            {
                "listing_id": listing_id,
                "bidder_account": "SBS-buyer001",
                "amount": 650,
            },
        )
        assert body["ok"] is True
        eco.store.close_listing(
            listing_id=listing_id, seller_account="SBS-seller01"
        )
        order = _pj(
            eco.sbs_base + "/subastas/api/orders",
            {
                "listing_id": listing_id,
                "buyer_account": "SBS-buyer001",
                "source": "auction",
            },
        )["data"]
        order_id = order["order_id"]
        assert order["subtotal"] == 650.0
        assert order["platform_fee"] == 32.5
        assert order["status"] == "created"
        listing_after = _gj(
            eco.sbs_base
            + "/subastas/api/listings/"
            + listing_id
        )["data"]
        assert listing_after["winner_account"] == "SBS-buyer001"
        assert listing_after["final_price"] == 650.0
        assert listing_after["closed_at"] is not None
        paid = _pj(
            eco.sbs_base + "/subastas/api/orders/" + order_id + "/pay",
            {"provider": "wallet"},
        )["data"]
        assert paid["status"] == "paid"
        assert paid["commission"]["commission_amount"] == 32.5
        settled = _pj(
            eco.sbs_base
            + "/subastas/api/orders/"
            + order_id
            + "/settle",
            {},
        )["data"]
        assert settled["settlement"]["net_amount"] == 617.5
        shipped = _pj(
            eco.sbs_base
            + "/subastas/api/orders/"
            + order_id
            + "/ship",
            {
                "carrier": "zyra-express",
                "origin": "San Salvador",
                "destination": "Santa Ana",
            },
        )["data"]
        assert shipped["status"] == "shipped"
        shipment_id = shipped["shipment"]["shipment_id"]
        tracked = _pj(
            eco.sbs_base
            + "/subastas/api/shipments/"
            + shipment_id
            + "/track",
            {
                "status": "in_transit",
                "location": "Ruta 1",
                "description": "en camino",
            },
        )["data"]
        assert tracked["status"] == "in_transit"
        delivered = _pj(
            eco.sbs_base
            + "/subastas/api/shipments/"
            + shipment_id
            + "/deliver",
            {},
        )["data"]
        assert delivered["status"] == "delivered"
        mutual = _pj(
            eco.sbs_base + "/subastas/api/reputation/mutual",
            {
                "order_id": order_id,
                "buyer_account": "SBS-buyer001",
                "seller_account": "SBS-seller01",
                "evidence": "moto entregada y pagada 650",
            },
        )["data"]
        assert mutual["buyer_to_seller_network"] is True, json.dumps(
            mutual
        )
        assert mutual["seller_to_buyer_network"] is True, json.dumps(
            mutual
        )
        assert mutual["history_seller_recorded"] is True, json.dumps(
            mutual
        )
        assert mutual["history_buyer_recorded"] is True, json.dumps(
            mutual
        )
    finally:
        eco.close()


def test_2_direct_purchase(tmp_path: Path) -> None:
    eco = _Eco(tmp_path)
    try:
        eco.register_app_canonical()
        eco.store.add_account(
            account_id="SBS-s2", zid=None, name="Vendedor Dos"
        )
        eco.store.add_account(
            account_id="SBS-b2", zid=None, name="Comprador Dos"
        )
        _pf(
            eco.sbs_base + "/subastas/listing",
            {
                "seller_account": "SBS-s2",
                "title": "Bicicleta",
                "description": "nueva",
                "base_price": 120,
            },
        )
        listing_id = eco.store.list_open()[0]["listing_id"]
        order = _pj(
            eco.sbs_base + "/subastas/api/orders",
            {
                "listing_id": listing_id,
                "buyer_account": "SBS-b2",
                "source": "direct",
            },
        )["data"]
        assert order["subtotal"] == 120.0
        assert order["platform_fee"] == 6.0
        paid = _pj(
            eco.sbs_base
            + "/subastas/api/orders/"
            + order["order_id"]
            + "/pay",
            {"provider": "cash"},
        )["data"]
        assert paid["status"] == "paid"
        settled = _pj(
            eco.sbs_base
            + "/subastas/api/orders/"
            + order["order_id"]
            + "/settle",
            {},
        )["data"]
        assert settled["settlement"]["net_amount"] == 114.0
        final_order = _gj(
            eco.sbs_base
            + "/subastas/api/orders/"
            + order["order_id"]
        )["data"]
        assert final_order["status"] == "settled"
    finally:
        eco.close()


def test_3_radar_vip(tmp_path: Path) -> None:
    eco = _Eco(tmp_path)
    try:
        scan = _pj(
            eco.sbs_base + "/subastas/api/radar/scan",
            {
                "title": "Moto en EEUU",
                "category": "vehiculos",
                "purchase_price": 100,
                "shipping_cost": 10,
                "fees": 5,
                "estimated_sale_price": 200,
                "demand_score": 0.8,
                "risk_score": 0.2,
            },
        )["data"]
        assert scan["total_cost"] == 115.0
        assert scan["expected_profit"] == 85.0
        assert scan["margin_percent"] == 73.91
        assert scan["opportunity_score"] == 76.95
        bad = _pj(
            eco.sbs_base + "/subastas/api/radar/scan",
            {
                "title": "Lote ropa",
                "category": "ropa",
                "purchase_price": 300,
                "shipping_cost": 20,
                "fees": 10,
                "estimated_sale_price": 320,
                "demand_score": 0.4,
                "risk_score": 0.6,
            },
        )["data"]
        assert bad["expected_profit"] == -10.0
        opportunities = _gj(
            eco.sbs_base + "/subastas/api/opportunities"
        )["data"]["opportunities"]
        assert len(opportunities) == 2
        revision = _h(eco.sbs_base + "/subastas/revision")
        assert "Revision SUBASTAS" in revision
        assert "oportunidades radar: 2" in revision
    finally:
        eco.close()


def test_4_offline_resilience(tmp_path: Path) -> None:
    db = SQLiteAdapter(tmp_path / "sbs.db")
    clock = FrozenClock()
    store = SubastasStore(db, clock)
    dead_client = NetworkClient(
        "http://127.0.0.1:1",
        timeout_seconds=1.0,
        max_retries=0,
    )
    server = serve_subastas(store, dead_client)
    thread = threading.Thread(
        target=server.serve_forever, daemon=True
    )
    thread.start()
    base = "http://127.0.0.1:" f"{server.bound_port}"
    try:
        store.add_account(
            account_id="SBS-off-s", zid=None, name="Vendedor Off"
        )
        store.add_account(
            account_id="SBS-off-b", zid=None, name="Comprador Off"
        )
        html = _pf(
            base + "/subastas/listing",
            {
                "seller_account": "SBS-off-s",
                "title": "Venta offline",
                "description": "sin red",
                "base_price": 80,
            },
        )
        assert "SELLADO" in html
        listing_id = store.list_open()[0]["listing_id"]
        body = _pj(
            base + "/subastas/api/bids",
            {
                "listing_id": listing_id,
                "bidder_account": "SBS-off-b",
                "amount": 90,
            },
        )
        assert body["ok"] is True
        store.close_listing(
            listing_id=listing_id, seller_account="SBS-off-s"
        )
        order = _pj(
            base + "/subastas/api/orders",
            {
                "listing_id": listing_id,
                "buyer_account": "SBS-off-b",
                "source": "auction",
            },
        )["data"]
        assert order["subtotal"] == 90.0
        paid = _pj(
            base
            + "/subastas/api/orders/"
            + order["order_id"]
            + "/pay",
            {"provider": "efectivo"},
        )["data"]
        assert paid["status"] == "paid"
        settled = _pj(
            base
            + "/subastas/api/orders/"
            + order["order_id"]
            + "/settle",
            {},
        )["data"]
        assert settled["settlement"]["net_amount"] == 85.5
        summary = _gj(base + "/subastas/api/summary")["summary"]
        assert summary["listings_total"] == 1
    finally:
        server.shutdown()
        server.server_close()
        thread.join(timeout=5)
        db.close()
