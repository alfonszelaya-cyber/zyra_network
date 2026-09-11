"""AGRO aid e2e - government aid full lifecycle over
real HTTP with the network; duplicates and wrong
order rejected; unverified producer rejected; new
aid screens served; original screens untouched."""
from __future__ import annotations

import json
import threading
from pathlib import Path
from urllib.error import HTTPError
from urllib.request import (
    Request,
    urlopen,
)

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
from apps.agro.services.zyra_link import (
    ZyraLink,
)


class _Ecosystem:
    def __init__(self, tmp_path: Path) -> None:
        self.net_db = SQLiteAdapter(
            tmp_path / "network.db"
        )
        signer, _ = Ed25519Signer.generate()
        self.kernel = ZyraKernel(
            db=self.net_db,
            clock=FrozenClock(),
            signer=signer,
            config=RuntimeConfig(
                host="127.0.0.1",
                port=0,
                api_token=None,
            ),
        )
        self.kernel.bootstrap_root()
        self.caps = ZyraCapabilities(
            self.net_db,
            FrozenClock(),
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
            target=self.net_server.serve_forever,
            daemon=True,
        )
        self.net_thread.start()
        self.net_base = (
            "http://127.0.0.1:"
            f"{self.net_server.server_address[1]}"
        )
        self.agro_db = SQLiteAdapter(
            tmp_path / "agro.db"
        )
        self.store = AgroStore(
            self.agro_db, FrozenClock()
        )
        self.client = NetworkClient(
            self.net_base, max_retries=1
        )
        self.link = ZyraLink(self.client)
        self.agro_server = serve_agro(
            self.store, self.client
        )
        self.agro_thread = threading.Thread(
            target=self.agro_server.serve_forever,
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


def _get(url: str) -> dict:
    with urlopen(url, timeout=10) as r:
        body = json.loads(
            r.read().decode("utf-8")
        )
    assert isinstance(body, dict)
    return body


def _post(url: str, doc: dict) -> dict:
    request = Request(
        url,
        data=json.dumps(doc).encode("utf-8"),
        headers={
            "Content-Type": "application/json"
        },
        method="POST",
    )
    with urlopen(request, timeout=10) as response:
        body = json.loads(
            response.read().decode("utf-8")
        )
    assert isinstance(body, dict)
    return body


def _post_status(url: str, doc: dict) -> int:
    request = Request(
        url,
        data=json.dumps(doc).encode("utf-8"),
        headers={
            "Content-Type": "application/json"
        },
        method="POST",
    )
    try:
        with urlopen(request, timeout=10) as response:
            return response.status
    except HTTPError as exc:
        return exc.code


def _get_html(url: str) -> str:
    with urlopen(url, timeout=10) as r:
        return r.read().decode("utf-8")


def test_aid_full_lifecycle(tmp_path: Path) -> None:
    eco = _Ecosystem(tmp_path)
    try:
        assert eco.link.register_app()[0] is True
        created = _post(
            eco.agro_base + "/agro/producers",
            {
                "name": "Jose Rural",
                "producer_type": "agricultor",
                "location": "Chalatenango",
            },
        )
        row = created["data"]
        producer_id = str(row["producer_id"])
        zid = row.get("zid")
        assert isinstance(zid, str)
        assert zid.startswith("ZID-")
        verified = _post(
            eco.agro_base + "/agro/producers/verify",
            {"producer_id": producer_id},
        )
        assert verified["data"]["verified"] is True
        aid = _post(
            eco.agro_base + "/agro/aid/request",
            {
                "producer_id": producer_id,
                "program": "semillas",
                "item": "maiz criollo",
                "quantity": 10,
            },
        )["data"]
        aid_id = str(aid["aid_id"])
        assert aid["status"] == "requested"
        assert aid["zid"] == zid
        assert (
            aid["events"][0]["network_seq"]
            is not None
        )
        dup = _post_status(
            eco.agro_base + "/agro/aid/request",
            {
                "producer_id": producer_id,
                "program": "semillas",
                "item": "maiz",
                "quantity": 3,
            },
        )
        assert dup == 400
        result = _post(
            eco.agro_base + "/agro/aid/eligibility",
            {"aid_id": aid_id},
        )["data"]
        assert result["status"] == "eligible"
        result = _post(
            eco.agro_base
            + "/agro/government/approve",
            {"aid_id": aid_id},
        )["data"]
        assert result["status"] == "approved"
        result = _post(
            eco.agro_base
            + "/agro/government/assign",
            {"aid_id": aid_id, "detail": "lote 7"},
        )["data"]
        assert result["status"] == "assigned"
        result = _post(
            eco.agro_base
            + "/agro/government/deliver",
            {
                "aid_id": aid_id,
                "detail": "entregado en centro",
            },
        )["data"]
        assert result["status"] == "delivered"
        result = _post(
            eco.agro_base
            + "/agro/government/confirm",
            {"aid_id": aid_id},
        )["data"]
        assert result["status"] == "confirmed"
        assert [
            e["transition"] for e in result["events"]
        ] == [
            "AID_REQUESTED",
            "AID_ELIGIBILITY_EVALUATED",
            "AID_APPROVED",
            "AID_ASSIGNED",
            "AID_DELIVERED",
            "AID_DELIVERY_CONFIRMED",
        ]
        detail = _get(
            eco.agro_base + "/agro/aid/" + aid_id
        )["data"]
        assert detail["status"] == "confirmed"
        created2 = _post(
            eco.agro_base + "/agro/producers",
            {
                "name": "Nuevo Sin Verificar",
                "producer_type": "agricultor",
            },
        )
        producer2 = str(
            created2["data"]["producer_id"]
        )
        aid2 = _post(
            eco.agro_base + "/agro/aid/request",
            {
                "producer_id": producer2,
                "program": "fertilizante",
                "item": "urea",
                "quantity": 5,
            },
        )["data"]
        rejected = _post(
            eco.agro_base + "/agro/aid/eligibility",
            {"aid_id": str(aid2["aid_id"])},
        )["data"]
        assert rejected["status"] == "rejected"
        bad = _post_status(
            eco.agro_base
            + "/agro/government/approve",
            {"aid_id": str(aid2["aid_id"])},
        )
        assert bad == 400
        ayudas = _get_html(
            eco.agro_base
            + "/agro/ayudas/"
            + producer_id
        )
        assert "Mis ayudas del Gobierno" in ayudas
        assert "semillas" in ayudas
        assert "confirmed" in ayudas
        gov_aid = _get_html(
            eco.agro_base + "/agro/ayudas"
        )
        assert "Ayudas gubernamentales" in gov_aid
        assert "semillas" in gov_aid
        assert "fertilizante" in gov_aid
        panel = _get_html(
            eco.agro_base
            + "/agro/productor/"
            + producer_id
        )
        assert "Mi Panel" in panel
        assert "Jose Rural" in panel
        gov = _get_html(
            eco.agro_base + "/agro/gobierno"
        )
        assert "Gobierno" in gov
        assert "Soberania" in gov
        summary = _get(
            eco.agro_base
            + "/agro/government/summary"
        )["data"]
        assert summary["producers_total"] == 2
        assert summary["aid_total"] == 2
        assert summary["aid_by_status"]["confirmed"] == 1
        assert summary["aid_by_status"]["rejected"] == 1
        assert "semillas" in summary["aid_by_program"]
        assert (
            "fertilizante"
            in summary["aid_by_program"]
        )
    finally:
        eco.close()
