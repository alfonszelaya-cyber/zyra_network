"""AGRO super-app e2e: navegacion por roles,
areas vivas con eventos, ley biometrica.
Fixs integrados: estado de venta 'created'
(contrato del store) y registro de app
(/apps/register) antes de usar caps de la Red."""
from __future__ import annotations

import json
import threading
import time
import urllib.error
import urllib.request
from pathlib import Path

from shared_engines.common.clocks import FrozenClock
from shared_engines.runtime.capabilities import ZyraCapabilities
from shared_engines.runtime.combined_api import serve_combined
from shared_engines.runtime.config import RuntimeConfig
from shared_engines.runtime.kernel import ZyraKernel
from shared_engines.security.biometrics import (
    BiometricsEngine,
    BiometricsPolicy,
    DeterministicTestProvider,
    TemplateCipher,
)
from shared_engines.storage.database import SQLiteAdapter
from shared_engines.verification.signatures import Ed25519Signer

from apps.agro.infrastructure.network.network_client import NetworkClient
from apps.agro.infrastructure.persistence.agro_store import AgroStore
from apps.agro.server import serve_agro
from apps.agro.services.zyra_link import ZyraLink


def _seed(name):
    return (name.strip().encode("utf-8").hex() + "zyra" * 16)[:64]


def _post(base, path, doc):
    req = urllib.request.Request(
        base + path,
        data=json.dumps(doc).encode(),
        headers={"Content-Type": "application/json"},
        method="POST")
    try:
        with urllib.request.urlopen(req, timeout=10) as r:
            return r.status, json.loads(r.read().decode())
    except urllib.error.HTTPError as e:
        body = e.read().decode("utf-8", "replace")
        raise AssertionError(
            "POST " + path + " -> HTTP "
            + str(e.code) + ": " + body[:400])


def _get(base, path):
    try:
        with urllib.request.urlopen(base + path, timeout=10) as r:
            return r.status, r.read().decode()
    except urllib.error.HTTPError as e:
        body = e.read().decode("utf-8", "replace")
        raise AssertionError(
            "GET " + path + " -> HTTP "
            + str(e.code) + ": " + body[:400])


def _register(base, name):
    st, body = _post(base, "/agro/producers", {
        "name": name,
        "producer_type": "agricultor",
        "location": "Chalatenango",
        "doc_image_b64": _seed(name),
        "selfie_image_b64": _seed(name),
    })
    assert st == 201, str(body)
    return body["data"]["producer_id"]


def test_navigation_by_roles(tmp_path: Path) -> None:
    dead = NetworkClient("http://127.0.0.1:1",
                         timeout_seconds=1.0, max_retries=0)
    srv = serve_agro(
        AgroStore(SQLiteAdapter(":memory:"), FrozenClock()), dead)
    threading.Thread(target=srv.serve_forever, daemon=True).start()
    time.sleep(0.4)
    base = f"http://127.0.0.1:{srv.bound_port}"
    pid = _register(base, "Maria Navega")
    _post(base, "/agro/production", {
        "producer_id": pid, "product": "maiz",
        "quantity": 50, "unit": "quintal"})
    _post(base, "/agro/land", {
        "producer_id": pid, "location": "Norte",
        "size_hectares": 10, "land_use": "maiz"})

    st, panel = _get(base, "/agro/productor/" + pid)
    assert st == 200
    assert "Mi Panel" in panel
    assert "Maria Navega" in panel
    assert "Registrar mi cosecha" in panel
    assert "Vender mi producto" in panel
    assert "Ayuda del Gobierno" in panel

    st, gov = _get(base, "/agro/gobierno")
    assert st == 200
    assert "Gobierno" in gov
    assert "Soberania" in gov
    assert "maiz" in gov
    assert "Beneficiados" in gov
    assert "Maria Navega" in gov
    assert "Modulos de la Red AGRO" in gov

    st, seg = _get(base, "/agro/gobierno/seguridad")
    assert st == 200 and "maiz" in seg

    st, ben = _get(base, "/agro/gobierno/beneficiados")
    assert st == 200
    assert "Maria Navega" in ben

    st, rsk = _get(base, "/agro/gobierno/riesgos")
    assert st == 200

    st, mkt = _get(base, "/agro/mercado")
    assert st == 200 and "maiz" in mkt

    st, bank = _get(base, "/agro/banco")
    assert st == 200
    assert "Banco" in bank and "credito" in bank

    st, body = _post(base, "/agro/sale", {
        "producer_id": pid, "buyer": "Exportador X",
        "product": "maiz", "quantity": 20,
        "unit": "quintal", "price": 400})
    assert st == 201, str(body)

    st, ar = _get(base, "/agro/areas/" + pid)
    d = json.loads(ar)["data"]
    assert len(d["lands"]) == 1
    assert d["sales"][0]["status"] == "created"


def test_areas_events_on_network(tmp_path: Path) -> None:
    net_db = SQLiteAdapter(tmp_path / "net.db")
    signer, _ = Ed25519Signer.generate()
    kernel = ZyraKernel(
        db=net_db, clock=FrozenClock(), signer=signer,
        config=RuntimeConfig(
            host="127.0.0.1", port=0, api_token=None))
    kernel.bootstrap_root()
    kernel._biometrics = BiometricsEngine(
        db=net_db, clock=FrozenClock(), audit=kernel.audit,
        provider=DeterministicTestProvider(),
        cipher=TemplateCipher(master_key_hex="ab" * 32),
        policy=BiometricsPolicy(
            require_liveness=False,
            doc_reject=0.01, doc_review=0.02,
            doc_auto=0.03, dup_reject=0.98))
    caps = ZyraCapabilities(
        net_db, FrozenClock(),
        identity=kernel.identity, signer=signer)
    net_srv = serve_combined(
        kernel, caps, host="127.0.0.1", port=0)
    threading.Thread(
        target=net_srv.serve_forever, daemon=True).start()
    time.sleep(0.4)
    net_base = f"http://127.0.0.1:{net_srv.server_address[1]}"

    client = NetworkClient(net_base, max_retries=1)
    reg = ZyraLink(client).register_app()
    assert reg[0] is True, (
        "apps/register fallo: " + str(reg[2]))

    srv = serve_agro(
        AgroStore(SQLiteAdapter(":memory:"), FrozenClock()),
        client)
    threading.Thread(
        target=srv.serve_forever, daemon=True).start()
    time.sleep(0.4)
    base = f"http://127.0.0.1:{srv.bound_port}"

    pid = _register(base, "Jose EnRed")
    st, body = _post(base, "/agro/sale", {
        "producer_id": pid, "buyer": "Exportador Intl",
        "product": "frijol", "quantity": 30,
        "unit": "quintal", "price": 800})
    assert st == 201, str(body)
    assert body["data"]["network_seq"] is not None, (
        "evento de venta no llego a la Red")
