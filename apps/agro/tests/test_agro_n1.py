"""AGRO N1 proofs: farmer journey over real HTTP
against the COMBINED network surface + resilience."""
from __future__ import annotations

import json
import threading
from pathlib import Path
from urllib.request import Request, urlopen

from shared_engines.common.clocks import FrozenClock
from shared_engines.runtime.capabilities import (
    ZyraCapabilities,
)
from shared_engines.runtime.combined_api import (
    serve_combined,
)
from shared_engines.runtime.config import RuntimeConfig
from shared_engines.runtime.kernel import ZyraKernel
from shared_engines.storage.database import SQLiteAdapter
from shared_engines.verification.signatures import (
    Ed25519Signer,
)

from apps.agro.infrastructure.network.network_client import (
    NetworkClient,
)
from apps.agro.infrastructure.persistence.agro_store import (
    AgroStore,
)
from apps.agro.server import serve_agro
from apps.agro.services.zyra_link import ZyraLink


class _Ecosystem:
    def __init__(self, tmp_path: Path) -> None:
        self.net_db = SQLiteAdapter(
            tmp_path / "network.db"
        )
        net_clock = FrozenClock()
        signer, _ = Ed25519Signer.generate()
        config = RuntimeConfig(
            host="127.0.0.1",
            port=0,
            api_token=None,
        )
        self.kernel = ZyraKernel(
            db=self.net_db,
            clock=net_clock,
            signer=signer,
            config=config,
        )
        self.kernel.bootstrap_root()
        self.caps = ZyraCapabilities(
            self.net_db,
            net_clock,
            identity=self.kernel.identity,
            signer=signer,
        )
        self.net_server = serve_combined(
            self.kernel,
            self.caps,
            host="127.0.0.1",
            port=0,
        )
        self.net_thread = threading.Thread(
            target=(
                self.net_server
                .serve_forever
            ),
            daemon=True,
        )
        self.net_thread.start()
        self.net_base = (
            "http://127.0.0.1:"
            f"{self.net_server.server_address[1]}"
        )
        self.net_url = self.net_base

        self.agro_db = SQLiteAdapter(
            tmp_path / "agro.db"
        )
        agro_clock = FrozenClock()
        self.store = AgroStore(
            self.agro_db, agro_clock
        )
        self.client = NetworkClient(
            self.net_url, max_retries=1
        )
        self.link = ZyraLink(self.client)
        self.agro_server = serve_agro(
            self.store, self.client
        )
        self.agro_thread = threading.Thread(
            target=(
                self.agro_server
                .serve_forever
            ),
            daemon=True,
        )
        self.agro_thread.start()
        self.agro_base = (
            "http://127.0.0.1:"
            f"{self.agro_server.bound_port}"
        )

    def close(self) -> None:
        self.agro_server.shutdown()
        self.agro_server.server_close()
        self.agro_thread.join(timeout=5)
        self.net_server.shutdown()
        self.net_server.server_close()
        self.net_thread.join(timeout=5)
        self.agro_db.close()
        self.net_db.close()


def _get(url: str) -> dict[str, object]:
    with urlopen(url, timeout=10) as response:
        body = json.loads(
            response.read().decode("utf-8")
        )
    assert isinstance(body, dict)
    return body


def _post(
    url: str, doc: dict[str, object]
) -> dict[str, object]:
    request = Request(
        url,
        data=json.dumps(doc).encode("utf-8"),
        headers={
            "Content-Type":
            "application/json"
        },
        method="POST",
    )
    with urlopen(request, timeout=10) as response:
        body = json.loads(
            response.read().decode("utf-8")
        )
    assert isinstance(body, dict)
    return body


def test_farmer_journey_end_to_end(
    tmp_path: Path,
) -> None:
    eco = _Ecosystem(tmp_path)
    try:
        reg = eco.link.register_app()
        assert reg[0] is True
        health = _get(
            f"{eco.agro_base}/agro/health"
        )
        assert health["ok"] is True
        created = _post(
            f"{eco.agro_base}/agro/producers",
            {
                "name": "Jose Rural",
                "producer_type":
                "agricultor",
                "location": "Chalatenango",
            },
        )
        row = created["data"]
        assert isinstance(row, dict)
        producer_id = str(
            row["producer_id"]
        )
        zid = row.get("zid")
        assert isinstance(zid, str)
        assert zid.startswith("ZID-")
        assert row["synced"] is True
        verified = _post(
            f"{eco.agro_base}/agro/producers/verify",
            {"producer_id": producer_id},
        )
        vdata = verified["data"]
        assert isinstance(vdata, dict)
        assert vdata["verified"] is True
        production = _post(
            f"{eco.agro_base}/agro/production",
            {
                "producer_id": producer_id,
                "product": "maiz",
                "quantity": 50,
                "unit": "quintal",
            },
        )
        pdata = production["data"]
        assert isinstance(pdata, dict)
        assert (
            pdata["network_seq"] is not None
        )
        summary = _get(
            f"{eco.agro_base}/agro/government/"
            "summary"
        )
        gdata = summary["data"]
        assert isinstance(gdata, dict)
        assert (
            gdata["producers_total"] == 1
        )
        assert (
            gdata["producers_verified"]
            == 1
        )
        by_product = gdata[
            "productions_by_product"
        ]
        assert isinstance(by_product, dict)
        assert by_product.get("maiz") == 50
        alert = _post(
            f"{eco.agro_base}/agro/alerts/"
            "evaluate",
            {
                "previous_price": 20.0,
                "current_price": 22.0,
            },
        )
        adata = alert["data"]
        assert isinstance(adata, dict)
        assert adata["alert"] is True
        assert adata["direction"] == "up"
    finally:
        eco.close()


def test_resilience_network_down_app_survives(
    tmp_path: Path,
) -> None:
    db = SQLiteAdapter(tmp_path / "agro.db")
    clock = FrozenClock()
    store = AgroStore(db, clock)
    dead_client = NetworkClient(
        "http://127.0.0.1:1",
        timeout_seconds=1.0,
        max_retries=0,
    )
    server = serve_agro(store, dead_client)
    thread = threading.Thread(
        target=server.serve_forever,
        daemon=True,
    )
    thread.start()
    base = (
        "http://127.0.0.1:"
        f"{server.bound_port}"
    )
    try:
        created = _post(
            f"{base}/agro/producers",
            {
                "name": "Maria Offline",
                "producer_type": (
                    "agricultora"
                ),
                "location": "Usulutan",
            },
        )
        row = created["data"]
        assert isinstance(row, dict)
        assert row.get("zid") is None
        assert row["synced"] is False
        production = _post(
            f"{base}/agro/production",
            {
                "producer_id": str(
                    row["producer_id"]
                ),
                "product": "frijol",
                "quantity": 10,
                "unit": "quintal",
            },
        )
        pdata = production["data"]
        assert isinstance(pdata, dict)
        assert (
            pdata["network_seq"] is None
        )
        summary = _get(
            f"{base}/agro/government/summary"
        )
        gdata = summary["data"]
        assert isinstance(gdata, dict)
        assert (
            gdata["producers_total"] == 1
        )
    finally:
        server.shutdown()
        server.server_close()
        thread.join(timeout=5)
        db.close()


def test_menu_silicon_valley_rule(
    tmp_path: Path,
) -> None:
    eco = _Ecosystem(tmp_path)
    try:
        menu = _get(
            f"{eco.agro_base}/agro/menu"
        )
        data = menu["data"]
        assert isinstance(data, dict)
        actions = data["actions"]
        assert isinstance(actions, list)
        assert len(actions) <= 2
    finally:
        eco.close()
