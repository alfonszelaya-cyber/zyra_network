"""NEXO vision e2e - document -> AI analysis with
provenance -> automatic ledger entry -> invoice
sealed on the network -> contador verifies and
certifies; duplicates rejected; resilience offline."""
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

from apps.nexo.infrastructure.network.network_client import NetworkClient
from apps.nexo.infrastructure.persistence.nexo_store import NexoStore
from apps.nexo.server import serve_nexo
from apps.nexo.services.nexo_link import NexoLink


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
        self.link = NexoLink(self.client)
        self.nexo_db = SQLiteAdapter(tmp_path / "nexo.db")
        self.store = NexoStore(self.nexo_db, FrozenClock())
        self.nexo_server = serve_nexo(self.store, self.client)
        threading.Thread(
            target=self.nexo_server.serve_forever, daemon=True
        ).start()
        self.nexo_base = (
            "http://127.0.0.1:"
            f"{self.nexo_server.bound_port}"
        )

    def close(self) -> None:
        self.nexo_server.shutdown()
        self.nexo_server.server_close()
        self.net_server.shutdown()
        self.net_server.server_close()
        self.nexo_db.close()
        self.net_db.close()


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


def _real_zid(eco, name: str, kind: str) -> str:
    ok, data, _err = eco.client.post(
        "/identity/register",
        {
            "kind": kind,
            "display_name": name,
            "actor": "nexo",
        },
    )
    assert ok is True and data is not None
    zid = str(data.get("zid"))
    assert zid.startswith("ZID-")
    eco.client.post(
        "/trust/complete", {"zid": zid, "actor": "nexo"}
    )
    return zid


def test_1_document_analysis_automatic_entry_sealed(
    tmp_path: Path,
) -> None:
    eco = _Eco(tmp_path)
    try:
        assert eco.link.register_app()[0] is True
        seller = _real_zid(eco, "Vendedor NEXO", "person")
        buyer = _real_zid(eco, "Comprador NEXO", "organization")
        response = _pj(
            eco.nexo_base + "/nexo/api/documents",
            {
                "content": (
                    "Factura de venta #001"
                    " mercaderia general"
                ),
                "seller_zid": seller,
                "buyer_zid": buyer,
                "amount": 250.0,
            },
        )["data"]
        document = response["document"]
        analysis = response["analysis"]
        operation = response["operation"]
        assert document["document_id"].startswith("DOC-")
        assert document["content_sha256"]
        assert len(document["content_sha256"]) == 64
        assert document["kind"] == "venta"
        assert document["synced"] is True
        assert document["invoice_id"] is not None
        assert analysis["model_id"] == "nexo-rules-classifier"
        assert analysis["model_version"] == "1.0"
        assert analysis["verdict"] == "classified"
        assert analysis["confidence"] == 0.95
        assert analysis["analysis_id"].startswith("ANA-")
        assert operation["seq"] == 1
        assert len(operation["entry_hash"]) == 64
        verify = _gj(
            eco.nexo_base + "/nexo/api/ledger/verify"
        )["data"]
        assert verify["chain_intact"] is True
        summary = _gj(
            eco.nexo_base + "/nexo/api/summary"
        )["data"]
        assert summary["operations_total"] == 1
        assert summary["by_kind"]["venta"]["count"] == 1
        detail = _gj(
            eco.nexo_base
            + "/nexo/api/documents/"
            + document["document_id"]
        )["data"]
        assert detail["analysis"]["model_id"] == (
            "nexo-rules-classifier"
        )
        assert detail["operation_seq"] == 1
    finally:
        eco.close()


def test_2_duplicate_document_rejected(tmp_path: Path) -> None:
    eco = _Eco(tmp_path)
    try:
        assert eco.link.register_app()[0] is True
        seller = _real_zid(eco, "Vendedor Dup", "person")
        buyer = _real_zid(eco, "Comprador Dup", "person")
        payload = {
            "content": "Factura de venta unica #777",
            "seller_zid": seller,
            "buyer_zid": buyer,
            "amount": 100.0,
        }
        first = _pj(
            eco.nexo_base + "/nexo/api/documents", payload
        )
        assert first["ok"] is True
        second = _pj(
            eco.nexo_base + "/nexo/api/documents", payload
        )
        assert second["ok"] is False
        assert second["error"]["type"] == "duplicate_document"
        summary = _gj(
            eco.nexo_base + "/nexo/api/summary"
        )["data"]
        assert summary["operations_total"] == 1
        review = _gj(
            eco.nexo_base + "/nexo/api/review"
        )["data"]
        assert review["duplicates_blocked"] == 1
        assert review["documents_total"] == 1
        assert review["chain_intact"] is True
    finally:
        eco.close()


def test_3_contador_verifica_y_certifica(tmp_path: Path) -> None:
    eco = _Eco(tmp_path)
    try:
        assert eco.link.register_app()[0] is True
        seller = _real_zid(eco, "Vendedor Cert", "person")
        company = _real_zid(eco, "Empresa Cert", "organization")
        _pj(
            eco.nexo_base + "/nexo/api/documents",
            {
                "content": (
                    "Factura de venta certificable #900"
                ),
                "seller_zid": seller,
                "buyer_zid": company,
                "amount": 500.0,
            },
        )
        review = _gj(
            eco.nexo_base + "/nexo/api/review"
        )["data"]
        assert review["chain_intact"] is True
        revision_html = _h(
            eco.nexo_base + "/nexo/revision"
        )
        assert "Revision del Contador" in revision_html
        assert "nexo-rules-classifier" in revision_html
        certify = _pj(
            eco.nexo_base + "/nexo/api/review/certify",
            {
                "subject_zid": seller,
                "issuer_zid": company,
            },
        )["data"]
        assert certify["issued"] is True
        credential_id = certify.get("credential_id")
        assert credential_id
        with urlopen(
            eco.net_base
            + "/verification/credentials/"
            + str(credential_id),
            timeout=15,
        ) as response:
            raw = response.read().decode("utf-8")
        assert "financial" in raw
    finally:
        eco.close()


def test_4_resilience_offline_document(tmp_path: Path) -> None:
    db = SQLiteAdapter(tmp_path / "nexo.db")
    clock = FrozenClock()
    store = NexoStore(db, clock)
    dead_client = NetworkClient(
        "http://127.0.0.1:1",
        timeout_seconds=1.0,
        max_retries=0,
    )
    server = serve_nexo(store, dead_client)
    thread = threading.Thread(
        target=server.serve_forever, daemon=True
    )
    thread.start()
    base = "http://127.0.0.1:" f"{server.bound_port}"
    try:
        request = Request(
            base + "/nexo/api/documents",
            data=json.dumps(
                {
                    "content": (
                        "Factura de compra offline #500"
                    ),
                    "seller_zid": "ZID-x",
                    "buyer_zid": "ZID-y",
                    "amount": 75.0,
                }
            ).encode("utf-8"),
            headers={"Content-Type": "application/json"},
            method="POST",
        )
        with urlopen(request, timeout=15) as r:
            body = json.loads(r.read().decode("utf-8"))
        assert body["ok"] is True
        document = body["data"]["document"]
        assert document["synced"] is False
        assert document["invoice_id"] is None
        operation = body["data"]["operation"]
        assert operation["seq"] == 1
        review = _gj(base + "/nexo/api/review")["data"]
        assert review["documents_total"] == 1
        assert review["chain_intact"] is True
        assert review["operations_total"] == 1
    finally:
        server.shutdown()
        server.server_close()
        thread.join(timeout=5)
        db.close()
