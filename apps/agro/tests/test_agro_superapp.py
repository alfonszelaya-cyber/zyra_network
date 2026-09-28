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
        headers={
                          "Content-Type": "application/json",
                          "X-ZYRA-Actor-Role": "agricultor",
                      },
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


# ====== PLUS: perfil/units/docs/planes/incidents ======


def _pj(url, doc, role="agricultor"):
    req = urllib.request.Request(
        url,
        data=json.dumps(doc).encode(),
        headers={
            "Content-Type": "application/json",
            "X-ZYRA-Actor-Role": role,
        },
        method="POST",
    )
    try:
        with urllib.request.urlopen(
            req, timeout=10
        ) as r:
            return r.status, json.loads(
                r.read().decode()
            )
    except urllib.error.HTTPError as e:
        try:
            return e.code, json.loads(
                e.read().decode()
            )
        except Exception:
            return e.code, {}


def _gjp(url):
    try:
        with urllib.request.urlopen(
            url, timeout=10
        ) as r:
            return r.status, json.loads(
                r.read().decode()
            )
    except urllib.error.HTTPError as e:
        try:
            return e.code, json.loads(
                e.read().decode()
            )
        except Exception:
            return e.code, {}


def _govj(url, doc):
    return _pj(url, doc, role="gobierno")


def test_plus_profile_units_docs_plans(
    tmp_path: Path,
) -> None:
    dead = NetworkClient(
        "http://127.0.0.1:1",
        timeout_seconds=1.0,
        max_retries=0,
    )
    srv = serve_agro(
        AgroStore(
            SQLiteAdapter(":memory:"), FrozenClock()
        ),
        dead,
    )
    threading.Thread(
        target=srv.serve_forever, daemon=True
    ).start()
    time.sleep(0.4)
    base = f"http://127.0.0.1:{srv.bound_port}"
    pid = _register(base, "Elena PLUS")

    st, body = _pj(
        base + "/agro/perfil",
        {
            "producer_id": pid,
            "phone": "12345678",
            "location": "Norte",
            "notes": "cafe",
        },
    )
    assert st == 200, str(body)
    assert body["data"]["changed"]
    st, body = _gjp(
        base + "/agro/perfil/" + pid
    )
    assert body["data"]["phone"] == "12345678"
    st, body = _gjp(
        base + "/agro/perfil/"
        + pid + "/history"
    )
    assert len(
        body["data"]["history"]
    ) >= 1

    st, body = _pj(
        base + "/agro/perfil",
        {"producer_id": pid, "phone": "abc"},
    )
    assert st == 400, "telefono invalido 400"

    st, body = _pj(base + "/agro/unit", {
        "producer_id": pid, "name": "Finca Uno",
    })
    assert st == 201, str(body)
    unit_id = body["data"]["unit_id"]

    st, body = _pj(base + "/agro/plan", {
        "producer_id": pid,
        "unit_id": unit_id,
        "crop": "cafe",
        "planned_quantity": 100,
    })
    assert st == 201, str(body)
    plan_id = body["data"]["plan_id"]
    st, body = _pj(
        base + "/agro/plan/cost",
        {
            "plan_id": plan_id,
            "concept": "insumos",
            "amount": 500,
            "currency": "GTQ",
        },
    )
    assert st == 201, str(body)
    st, body = _pj(
        base + "/agro/plan/cost",
        {
            "plan_id": plan_id,
            "concept": "jornales",
            "amount": 100,
            "currency": "USD",
        },
    )
    assert st == 201, str(body)
    st, body = _gjp(
        base + "/agro/plans/"
        + plan_id + "/costs"
    )
    d = body["data"]
    assert d["total_by_currency"]["GTQ"] == 500.0
    assert d["total_by_currency"]["USD"] == 100.0

    st, body = _pj(
        base + "/agro/unit/close",
        {
            "unit_id": unit_id,
            "reason": "venta de tierra",
            "producer_id": pid,
        },
    )
    assert st == 200, str(body)
    st, body = _gjp(
        base + "/agro/units/"
        + pid + "/capacity"
    )
    d = body["data"]
    assert d["units_total"] == 1
    assert d["units_active"] == 0

    st, body = _pj(
        base + "/agro/document",
        {
            "producer_id": pid,
            "doc_kind": "pasaporte",
            "content_b64": "abc",
        },
    )
    assert st == 400, "tipo invalido 400"
    st, body = _pj(base + "/agro/document", {
        "producer_id": pid,
        "doc_kind": "dui",
        "content_b64": "c2VtYXBh",
    })
    assert st == 201, str(body)
    doc_id = body["data"]["doc_id"]
    assert body["data"]["content_sha256"]
    st, body = _gjp(base + "/agro/docs/" + pid)
    assert len(
        body["data"]["documents"]
    ) == 1
    st, body = _govj(
        base + "/agro/document/verify",
        {
            "doc_id": doc_id,
            "approve": "false",
            "note": "ilegible",
        },
    )
    assert st == 200, str(body)
    assert body["data"]["status"] == "rejected"
    st, body = _govj(
        base + "/agro/document/verify",
        {
            "doc_id": doc_id,
            "approve": "true",
            "note": "ok",
        },
    )
    assert st == 200, str(body)
    assert body["data"]["status"] == "verified"
    assert body["data"]["expiry_at"]


def test_plus_plans_stages_incidents_timeline(
    tmp_path: Path,
) -> None:
    dead = NetworkClient(
        "http://127.0.0.1:1",
        timeout_seconds=1.0,
        max_retries=0,
    )
    srv = serve_agro(
        AgroStore(
            SQLiteAdapter(":memory:"), FrozenClock()
        ),
        dead,
    )
    threading.Thread(
        target=srv.serve_forever, daemon=True
    ).start()
    time.sleep(0.4)
    base = f"http://127.0.0.1:{srv.bound_port}"
    pid = _register(base, "Fabio Etapas")
    st, body = _pj(base + "/agro/unit", {
        "producer_id": pid, "name": "Parcela",
    })
    unit_id = body["data"]["unit_id"]
    st, body = _pj(base + "/agro/plan", {
        "producer_id": pid,
        "unit_id": unit_id,
        "crop": "frijol",
        "planned_quantity": 100,
    })
    assert st == 201, str(body)
    plan_id = body["data"]["plan_id"]

    st, body = _pj(base + "/agro/plan", {
        "producer_id": pid,
        "unit_id": "UNI-fantasma",
        "crop": "maiz",
        "planned_quantity": 10,
    })
    assert st in (400, 404), "unidad fantasma"
    assert body.get("ok") is False

    for expected in (
        "planted", "growing", "harvested"
    ):
        st, body = _pj(
            base + "/agro/plan/advance",
            {"plan_id": plan_id},
        )
        assert st == 200, str(body)
        assert (
            body["data"]["to_stage"]
            == expected
        )
    st, body = _pj(
        base + "/agro/plan/advance",
        {"plan_id": plan_id},
    )
    assert st == 400, "pasado harvested 400"

    st, body = _gjp(base + "/agro/plans/" + pid)
    plans = body["data"]["plans"]
    assert len(plans) == 1
    assert plans[0]["status"] == "harvested"

    st, body = _pj(base + "/agro/incident", {
        "producer_id": pid,
        "kind": "plaga",
        "severity": "critica",
        "detail": "mosca blanca",
    })
    assert st == 201, str(body)
    assert body["data"]["escalated"] is True
    inc_id = body["data"]["incident_id"]
    st, body = _pj(base + "/agro/incident", {
        "producer_id": pid,
        "kind": "x",
        "severity": "ultra",
    })
    assert st == 400, "severidad invalida 400"
    st, body = _govj(
        base + "/agro/incident/resolve",
        {"incident_id": inc_id},
    )
    assert st == 400, "sin accion 400"
    st, body = _govj(
        base + "/agro/incident/resolve",
        {
            "incident_id": inc_id,
            "action": "fumigacion total",
        },
    )
    assert st == 200, str(body)
    assert body["data"]["status"] == "resolved"

    st, body = _gjp(
        base + "/agro/incidents/"
        + pid + "/stats"
    )
    stats = body["data"]
    assert stats["total"] == 1
    assert stats["by_status"]["resolved"] == 1

    _pj(base + "/agro/production", {
        "producer_id": pid,
        "product": "frijol",
        "quantity": 80,
        "unit": "quintal",
    })
    st, body = _gjp(base + "/agro/yield/" + pid)
    d = body["data"]
    assert d["planned_harvested"] == 100.0
    assert d["produced"] == 80.0
    assert d["efficiency"] == 0.8
    assert d["expected_remaining"] == 20.0

    st, body = _gjp(
        base + "/agro/plans/"
        + pid + "/timeline"
    )
    tl = body["data"]["timelines"]
    assert len(tl) >= 1
    kinds = [
        x["kind"] for x in tl[0]["timeline"]
    ]
    assert "stage" in kinds

    st, body = _gjp(
        base + "/agro/production/report"
    )
    assert body["data"]["total_records"] >= 1


# ====== RUN D: GPT-3 comercializacion ======


def test_commerce_full_cycle(tmp_path: Path) -> None:
    dead = NetworkClient(
        "http://127.0.0.1:1",
        timeout_seconds=1.0,
        max_retries=0,
    )
    srv = serve_agro(
        AgroStore(
            SQLiteAdapter(":memory:"), FrozenClock()
        ),
        dead,
    )
    threading.Thread(
        target=srv.serve_forever, daemon=True
    ).start()
    time.sleep(0.4)
    base = f"http://127.0.0.1:{srv.bound_port}"
    pid = _register(base, "Gustavo Vende")

    st, body = _pj(
        base + "/agro/inventory/add",
        {
            "producer_id": pid,
            "product": "cafe",
            "quantity": 100,
            "unit": "quintal",
        },
    )
    assert st == 201, str(body)

    st, body = _pj(
        base + "/agro/sale/publish",
        {
            "producer_id": pid,
            "product": "cafe",
            "quantity": 50,
            "unit": "quintal",
            "currency": "USD",
        },
    )
    assert st == 201, str(body)
    sale_id = body["data"]["sale_id"]
    assert body["data"]["status"] == "listed"
    assert body["data"]["remaining"] == 50.0

    st, body = _pj(
        base + "/agro/sale/publish",
        {
            "producer_id": pid,
            "product": "cafe",
            "quantity": -5,
        },
    )
    assert st == 400, "cantidad negativa 400"

    st, body = _pj(
        base + "/agro/sale/offer",
        {
            "sale_id": sale_id,
            "buyer": "Exportador X",
            "amount": 180,
            "currency": "USD",
        },
    )
    assert st == 201, str(body)
    offer_id = body["data"]["offer_id"]

    st, body = _pj(
        base + "/agro/sale/offer",
        {
            "sale_id": sale_id,
            "buyer": "Y",
            "amount": 100,
            "currency": "GTQ",
        },
    )
    assert st == 400, "moneda distinta 400"

    st, body = _pj(
        base + "/agro/sale/offer",
        {
            "sale_id": sale_id,
            "buyer": "Z",
            "amount": -3,
        },
    )
    assert st == 400, "oferta negativa 400"

    st, body = _pj(
        base + "/agro/sale/accept",
        {"offer_id": offer_id},
    )
    assert st == 200, str(body)
    assert body["data"]["total"] == 9000.0

    st, body = _pj(
        base + "/agro/sale/pay",
        {"sale_id": sale_id},
    )
    assert st == 200, str(body)
    assert body["data"]["status"] == "paid"
    assert body["data"]["total"] == 9000.0

    st, body = _pj(
        base + "/agro/sale/close",
        {"sale_id": sale_id},
    )
    assert st == 400, "cierre sin entrega 400"

    st, body = _pj(
        base + "/agro/sale/deliver",
        {"sale_id": sale_id},
    )
    assert st == 200, str(body)
    assert body["data"]["status"] == "delivered"

    st, body = _pj(
        base + "/agro/sale/close",
        {"sale_id": sale_id},
    )
    assert st == 200, str(body)
    assert body["data"]["status"] == "closed"
    assert (
        body["data"]["inventory_deducted"][
            "quantity"
        ]
        == 50.0
    )

    st, body = _gjp(
        base + "/agro/inventory/" + pid
    )
    inv = body["data"]["inventory"]
    assert len(inv) == 1
    assert inv[0]["quantity"] == 50.0

    st, body = _gjp(
        base + "/agro/results/" + pid
    )
    d = body["data"]
    assert d["sales_count"] == 1, str(d)
    assert d["total"] == 9000.0, str(d)

    st, body = _pj(
        base + "/agro/sale/pay",
        {"sale_id": sale_id},
    )
    assert st == 400, "re-pago 400"

    st, body = _pj(
        base + "/agro/sale/offer",
        {
            "sale_id": sale_id,
            "buyer": "Tarde",
            "amount": 10,
        },
    )
    assert st == 400, "oferta sobre cerrada 400"


def test_commerce_market_exports_shipments(
    tmp_path: Path,
) -> None:
    dead = NetworkClient(
        "http://127.0.0.1:1",
        timeout_seconds=1.0,
        max_retries=0,
    )
    srv = serve_agro(
        AgroStore(
            SQLiteAdapter(":memory:"), FrozenClock()
        ),
        dead,
    )
    threading.Thread(
        target=srv.serve_forever, daemon=True
    ).start()
    time.sleep(0.4)
    base = f"http://127.0.0.1:{srv.bound_port}"
    pid = _register(base, "Hilda Exporta")

    for p_ in (10, 12, 14):
        st, body = _pj(
            base + "/agro/market/price",
            {
                "product": "cafe",
                "price": p_,
            },
        )
        assert st == 201, str(body)

    st, body = _gjp(
        base + "/agro/market/price/cafe"
    )
    d = body["data"]
    assert d["minimum"] == 10.0
    assert d["maximum"] == 14.0
    assert d["average"] == 12.0

    st, body = _gjp(
        base + "/agro/market/price/oregano"
    )
    assert st == 400, "sin precios 400"

    st, body = _pj(
        base + "/agro/export",
        {
            "producer_id": pid,
            "product": "cafe",
            "destination": "Belgica",
            "quantity": 30,
        },
    )
    assert st == 201, str(body)
    assert body["data"]["status"] == "planned"
    st, body = _gjp(
        base + "/agro/exports/" + pid
    )
    assert len(body["data"]["exports"]) == 1

    st, body = _pj(
        base + "/agro/sale/publish",
        {
            "producer_id": pid,
            "product": "cafe",
            "quantity": 20,
            "currency": "USD",
        },
    )
    sale_id = body["data"]["sale_id"]
    st, body = _pj(
        base + "/agro/shipment",
        {
            "sale_id": sale_id,
            "origin": "Finca",
            "destination": "Puerto",
            "cargo": "20 qq cafe",
        },
    )
    assert st == 201, str(body)
    assert body["data"]["engine"] == (
        "zyra_network.logistics"
    )
    shipment_id = body["data"]["shipment_id"]

    st, body = _pj(
        base + "/agro/shipment/update",
        {
            "shipment_id": shipment_id,
            "status": "volando",
        },
    )
    assert st == 400, "estado invalido 400"
    st, body = _pj(
        base + "/agro/shipment/update",
        {
            "shipment_id": shipment_id,
            "status": "in_transit",
        },
    )
    assert st == 200, str(body)
