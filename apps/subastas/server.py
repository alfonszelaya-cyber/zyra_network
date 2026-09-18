"""ZYRA MARKET (antes SUBASTAS). Todas las rutas y
logica originales conservadas. HTML construido con
listas + join (sin concatenaciones fragiles)."""
from __future__ import annotations

import base64 as _b64
import hashlib
import json
from http.server import (
    BaseHTTPRequestHandler,
    ThreadingHTTPServer,
)
from urllib.parse import parse_qs

from apps.subastas.infrastructure.persistence.subastas_store import (
    SubastasStore,
    new_bid_id,
    new_listing_id,
)
from apps.subastas.infrastructure.persistence.subastas_commerce import (
    CommerceStore,
    _nid,
)


import importlib as _imp
_riesgo_mod = _imp.import_module(
    "apps.subastas.modules.009_riesgo_proteccion.riesgo_store"
)
_accounts_mod = _imp.import_module(
    "apps.subastas.modules.002_inscripciones.inscripciones_store"
)
_iext_mod = _imp.import_module(
    "apps.subastas.modules.002_inscripciones.inscripciones_ext"
)
_eje_mod = _imp.import_module(
    "apps.subastas.modules.001_ejecutivo.ejecutivo_store"
)
_tdr_mod = _imp.import_module(
    "apps.subastas.modules.005_bolsa_mercados.tiendas_store"
)
TiendasStore = _tdr_mod.TiendasStore
market_tiendas_page = _tdr_mod.market_tiendas_page
market_gov_tiendas_page = _tdr_mod.market_gov_tiendas_page
market_tiendas_api = _tdr_mod.market_tiendas_api
market_gov_tiendas_api = _tdr_mod.market_gov_tiendas_api
EjecutivoStore = _eje_mod.EjecutivoStore
market_dashboard_page = _eje_mod.market_dashboard_page
market_dashboard_api = _eje_mod.market_dashboard_api
InscripcionesExt = _iext_mod.InscripcionesExt
market_ins_ext_page = _iext_mod.market_ins_ext_page
market_gov_inscripcion_page = _iext_mod.market_gov_inscripcion_page
market_entity_register = _iext_mod.market_entity_register
market_doc_submit = _iext_mod.market_doc_submit
market_pm_add = _iext_mod.market_pm_add
market_verify_entity = _iext_mod.market_verify_entity
market_verify_document = _iext_mod.market_verify_document
RiesgoStore = _riesgo_mod.RiesgoStore
market_disputes_page = _riesgo_mod.market_disputes_page
market_fraud_page = _riesgo_mod.market_fraud_page
market_dispute_detail = _riesgo_mod.market_dispute_detail
market_dispute_open = _riesgo_mod.market_dispute_open
market_dispute_action = _riesgo_mod.market_dispute_action
market_fraud_flag = _riesgo_mod.market_fraud_flag
market_riesgo_page = _riesgo_mod.market_riesgo_page
market_riesgo_scan = _riesgo_mod.market_riesgo_scan
market_riesgo_block = _riesgo_mod.market_riesgo_block
AccountsStore = _accounts_mod.AccountsStore
market_inscripcion_page = _accounts_mod.market_inscripcion_page
market_login = _accounts_mod.market_login
market_logout = _accounts_mod.market_logout
market_register_user = _accounts_mod.market_register_user
market_update_profile = _accounts_mod.market_update_profile
market_link_zid = _accounts_mod.market_link_zid
market_register_company = _accounts_mod.market_register_company
market_gobierno_page = _accounts_mod.market_gobierno_page
market_verify_company = _accounts_mod.market_verify_company
_sess_user = _accounts_mod._sess_user
_require_role = _accounts_mod._require_role
# (accounts via importlib)
def _find_value(doc, keys):
    if isinstance(doc, dict):
        for k, v in doc.items():
            if str(k).lower() in keys:
                return v
        for v in doc.values():
            found = _find_value(v, keys)
            if found is not None:
                return found
    elif isinstance(doc, list):
        for item in doc:
            found = _find_value(item, keys)
            if found is not None:
                return found
    return None


class SubastasApiHandler(BaseHTTPRequestHandler):
    store: SubastasStore
    net_client: object

    def log_message(self, format: str, *args) -> None:
        pass

    def _send_bytes(self, status, ctype, body):
        self.send_response(status)
        self.send_header("Content-Type", ctype)
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def _send_html(self, status, html):
        self._send_bytes(status, "text/html", html.encode("utf-8"))

    def _send_json(self, status, doc):
        self._send_bytes(
            status, "application/json", json.dumps(doc).encode("utf-8")
        )

    def _read_body(self) -> bytes:
        try:
            length = int(self.headers.get("Content-Length", "0") or "0")
        except Exception:
            length = 0
        if length <= 0:
            return b""
        return self.rfile.read(length)

    def _read_form(self) -> dict:
        raw = self._read_body()
        parsed = parse_qs(raw.decode("utf-8"))
        form = {}
        for key, values in parsed.items():
            if values:
                form[key] = values[0]
        return form

    def _read_json(self):
        raw = self._read_body()
        if not raw:
            return {}
        try:
            doc = json.loads(raw.decode("utf-8"))
        except Exception:
            return None
        if not isinstance(doc, dict):
            return None
        return doc

    @staticmethod
    def _form_value(form, key):
        value = form.get(key, "")
        if value is None:
            return ""
        return str(value)

    def _seal_listing(self, seller, title, description, base_price):
        content = "|".join(
            (seller, title, description, format(base_price, ".2f"))
        )
        digest = hashlib.sha256(content.encode("utf-8")).hexdigest()
        candidates = (
            {"title": title, "sha256": digest, "kind": "listing"},
            {"title": title, "content_sha256": digest, "kind": "listing"},
            {"sha256": digest},
            {"content": content},
        )
        for payload in candidates:
            ok, data, _err = self.net_client.post("/documents/seal", payload)
            if ok and data:
                doc_id = _find_value(data, ("document_id", "seal_id"))
                if isinstance(doc_id, str) and doc_id:
                    return doc_id
        return "DOC-%s" % digest[:16]

    def do_GET(self) -> None:
        path = self.path.split("?")[0]
        try:
            if path in ("/", "/subastas", "/subastas/"):
                self._send_html(200, self._home())
                return
            if path in ("/subastas/api/health", "/subastas/health"):
                self._send_json(200, {"ok": True, "app": "subastas"})
                return
            if path == "/subastas/menu":
                self._send_html(200, self._page_menu())
                return
            if path == "/subastas/vendedor":
                self._send_html(200, self._page_vendedor())
                return
            if path == "/subastas/comprador":
                self._send_html(200, self._page_comprador())
                return
            if path == "/subastas/operaciones":
                self._send_html(200, self._page_operaciones())
                return
            if path == "/subastas/gobierno":
                self._send_html(200, self._page_gobierno())
                return
            if path.startswith("/subastas/order/"):
                self._send_html(200, self._order_html(path.split("/subastas/order/", 1)[1]))
                return
            if path == "/subastas/listings":
                self._send_html(200, self._listings_html())
                return
            if path.startswith("/subastas/api/listings/"):
                listing = self.commerce.get_listing_full(
                    path.split("/subastas/api/listings/", 1)[1]
                )
                if listing is None:
                    self._send_json(200, {"ok": False, "error": "unknown listing"})
                    return
                self._send_json(200, {"ok": True, "data": listing})
                return
            if path == "/subastas/api/opportunities":
                self._send_json(
                    200,
                    {"ok": True, "data": {"opportunities": self.commerce.list_opportunities()}},
                )
                return
            if path == "/subastas/revision":
                self._send_html(200, self._revision_html())
                return
            if path.startswith("/subastas/api/orders/"):
                self._send_json(
                    200,
                    {"ok": True, "data": self.commerce.get_order(path.split("/subastas/api/orders/", 1)[1])},
                )
                return
            if path.startswith("/subastas/api/shipments/"):
                self._send_json(
                    200,
                    {"ok": True, "data": self.commerce.get_shipment(path.split("/subastas/api/shipments/", 1)[1])},
                )
                return
            if path == "/subastas/tienda":
                self._send_html(200, self.market_tiendas_page())
                return
            if path == "/subastas/gov-tiendas":
                self._send_html(200, self.market_gov_tiendas_page())
                return
            if path == "/subastas/dashboard":
                self._send_html(200, self.market_dashboard_page())
                return
            if path == "/subastas/mi-inscripcion":
                self._send_html(200, self.market_ins_ext_page())
                return
            if path == "/subastas/gov-inscripcion":
                self._send_html(200, self.market_gov_inscripcion_page())
                return
            if path == "/subastas/inscripcion":
                self._send_html(200, self.market_inscripcion_page())
                return
            if path == "/subastas/gobierno-kyb":
                self._send_html(200, self.market_gobierno_page())
                return
            if path == "/subastas/proteccion":
                self._send_html(200, self.market_disputes_page())
                return
            if path == "/subastas/riesgo":
                self._send_html(200, self.market_riesgo_page())
                return
            if path == "/subastas/fraude":
                self._send_html(200, self.market_fraud_page())
                return
            if path.startswith("/subastas/disputa/"):
                self._send_html(
                    200,
                    self.market_dispute_detail(
                        path.split("/subastas/disputa/", 1)[1]
                    ),
                )
                return
            if path == "/subastas/api/summary":
                self._send_json(200, {"ok": True, "summary": self.store.summary()})
                return
            self._send_json(404, {"ok": False, "error": "unknown path: %s" % path})
        except Exception:
            self._send_json(500, {"ok": False, "error": "server error"})

    def do_POST(self) -> None:
        path = self.path.split("?")[0]
        try:
            if path == "/subastas/api/tiendas":
                self.market_tiendas_api()
                return
            if path == "/subastas/api/gov-tiendas":
                self.market_gov_tiendas_api()
                return
            if path == "/subastas/api/dashboard":
                self.market_dashboard_api()
                return
            if path == "/subastas/register":
                self._register_bio()
                return
            if path == "/subastas/listing":
                self._create_listing_form()
                return
            if path == "/subastas/api/bids":
                self._create_bid_json()
                return
            if path == "/subastas/api/orders":
                self._create_order_json()
                return
            if path == "/subastas/api/reputation/mutual":
                self._mutual_reputation_json()
                return
            if path == "/subastas/api/radar/scan":
                self._radar_scan_json()
                return
            if path.startswith("/subastas/api/orders/"):
                rest = path.split("/subastas/api/orders/", 1)[1]
                parts = rest.split("/")
                self._order_action(parts[0], parts[1] if len(parts) > 1 else "")
                return
            if path.startswith("/subastas/api/shipments/"):
                rest = path.split("/subastas/api/shipments/", 1)[1]
                parts = rest.split("/")
                self._shipment_action(parts[0], parts[1] if len(parts) > 1 else "")
                return
            if path == "/subastas/api/inscripcion/entidad":
                self.market_entity_register()
                return
            if path == "/subastas/api/inscripcion/documento":
                self.market_doc_submit()
                return
            if path == "/subastas/api/inscripcion/pago":
                self.market_pm_add()
                return
            if path == "/subastas/api/inscripcion/verificar-entidad":
                self.market_verify_entity()
                return
            if path == "/subastas/api/inscripcion/verificar-documento":
                self.market_verify_document()
                return
            if path == "/subastas/login":
                self.market_login()
                return
            if path == "/subastas/logout":
                self.market_logout()
                return
            if path == "/subastas/registro":
                self.market_register_user()
                return
            if path == "/subastas/perfil":
                self.market_update_profile()
                return
            if path == "/subastas/vincular":
                self.market_link_zid()
                return
            if path == "/subastas/empresa":
                self.market_register_company()
                return
            if path == "/subastas/api/empresa/verificar":
                self.market_verify_company()
                return
            if path == "/subastas/api/disputes":
                self.market_dispute_open()
                return
            if path == "/subastas/api/riesgo/scan":
                self.market_riesgo_scan()
                return
            if path == "/subastas/api/riesgo/bloqueo":
                self.market_riesgo_block()
                return
            if path == "/subastas/api/fraud":
                self.market_fraud_flag()
                return
            if path.startswith("/subastas/api/disputes/"):
                rest = path.split("/subastas/api/disputes/", 1)[1]
                parts = rest.split("/")
                self.market_dispute_action(
                    parts[0], parts[1] if len(parts) > 1 else ""
                )
                return
            if path == "/subastas/close":
                self._close_form()
                return
            self._send_json(404, {"ok": False, "error": "unknown path: %s" % path})
        except (ValueError, LookupError, PermissionError) as exc:
            self._send_json(400, {"ok": False, "error": str(exc)})
        except Exception:
            self._send_json(500, {"ok": False, "error": "server error"})

    def _create_listing_form(self) -> None:
        form = self._read_form()
        seller_account = self._form_value(form, "seller_account")
        title = self._form_value(form, "title")
        description = self._form_value(form, "description")
        raw_price = self._form_value(form, "base_price")
        if not seller_account or not title:
            self._send_html(400,
                "<html><body><h1>Faltan datos</h1></body></html>")
            return
        if self.riesgo.is_blocked(seller_account):
            raise PermissionError(
                "cuenta bloqueada por proteccion: " + seller_account
            )
        try:
            base_price = float(raw_price)
        except (TypeError, ValueError):
            self._send_html(400,
                "<html><body><h1>Precio invalido</h1></body></html>")
            return
        account = self.store.get_account(seller_account)
        seller_zid = account["zid"] if account else None
        document_id = self._seal_listing(
            seller_account, title, description, base_price)
        listing_id = new_listing_id()
        self.store.add_listing(
            listing_id=listing_id,
            seller_account=seller_account,
            seller_zid=seller_zid,
            title=title,
            description=description,
            base_price=base_price,
            document_id=document_id,
        )
        self._send_html(200, "".join([
            "<html><body><h1>ZYRA MARKET</h1>",
            "<p>SELLADO</p>",
            "<p>listing: %s</p>" % listing_id,
            "<p>documento: %s</p>" % document_id,
            "<p><a href='/subastas/menu'><button>Volver</button></a></p>",
            "</body></html>",
        ]))
    def _create_bid_json(self) -> None:
        doc = self._read_json()
        if doc is None:
            self._send_json(400, {"ok": False, "error": "invalid JSON"})
            return
        bidder = str(doc.get("bidder_account", ""))
        if self.riesgo.is_blocked(bidder):
            raise PermissionError(
                "cuenta bloqueada por proteccion: " + bidder
            )
        bid = self.store.place_bid(
            bid_id=new_bid_id(),
            listing_id=str(doc.get("listing_id", "")),
            bidder_account=bidder,
            amount=float(doc.get("amount", 0)),
        )
        self._send_json(200, {"ok": True, "bid": bid})
    def _close_form(self) -> None:
        form = self._read_form()
        closed = self.store.close_listing(
            listing_id=self._form_value(form, "listing_id"),
            seller_account=self._form_value(form, "seller_account"),
        )
        self._send_html(200, "".join([
            "<html><body><h1>ZYRA MARKET</h1>",
            "<p>GANADOR: %s</p>" % str(closed["winner_account"]),
            "<p>PRECIO FINAL: %s</p>" % format(closed["final_price"], ".2f"),
            "<p><a href='/subastas/menu'><button>Volver al menu</button></a></p>",
            "</body></html>",
        ]))

    def _register_bio(self) -> None:
        length = int(self.headers.get("Content-Length", 0) or 0)
        raw = self.rfile.read(length) if length > 0 else b""
        form = parse_qs(raw.decode("utf-8"))

        def _fv(key):
            vals = form.get(key, [])
            return vals[0] if vals else ""

        name = _fv("name").strip()
        doc_b64 = _fv("doc_image_b64").strip()
        selfie_b64 = _fv("selfie_image_b64").strip()
        if not name or not doc_b64 or not selfie_b64:
            self._bio_page(400, "<h2>Faltan datos obligatorios (por ley): nombre, foto del documento y selfie.</h2>", True)
            return
        ok, data, err = self.net_client.post(
            "/identity/enroll",
            {
                "kind": "person",
                "display_name": name,
                "actor": "subastas",
                "doc_image_b64": doc_b64,
                "selfie_image_b64": selfie_b64,
            },
        )
        zid = None
        if ok and data:
            found = _find_value(data, ("zid",))
            if isinstance(found, str) and found.startswith("ZID-"):
                zid = found
        if not ok or zid is None:
            msg = str(err) if err else "la red no devolvio ZID"
            self._bio_page(400, "<h2>Registro rechazado</h2><p>%s</p>" % msg, True)
            return
        self._bio_page(
            200,
            "".join([
                "<h2>Registro biometrico aprobado</h2>",
                "<p>Tu ZID: <b>%s</b></p>" % zid,
                "<p>Usa ese ZID como tu cuenta de vendedor o comprador al publicar y ofertar.</p>",
            ]),
            False,
        )

    def _bio_page(self, status, body, back) -> None:
        extra = "<p><a href='/'><button>Volver</button></a></p>" if back else ""
        html = "".join([
            "<html><head><meta charset='utf-8'>",
            "<title>ZYRA MARKET Registro</title></head>",
            "<body style='font-family:sans-serif;max-width:560px;margin:24px auto'>",
            "<h1>ZYRA MARKET</h1>",
            body,
            extra,
            "</body></html>",
        ])
        self._send_html(status, html)

    def _ensure_trusted_zid(self, account_id: str) -> str:
        zid = None
        existing = self.commerce.account_zid(account_id)
        if isinstance(existing, str) and existing.startswith("ZID-"):
            zid = existing
        if zid is None:
            raise ValueError(
                "cuenta sin ZID biometrico: registrese con documento y selfie"
                " en la pagina principal de ZYRA MARKET (%s)" % account_id
            )
        try:
            self.net_client.post("/trust/complete", {"zid": zid, "actor": "subastas"})
        except Exception:
            pass
        return zid

    def _create_order_json(self) -> None:
        doc = self._read_json()
        if doc is None:
            self._send_json(400, {"ok": False, "error": "invalid JSON"})
            return
        source = str(doc.get("source", "direct"))
        buyer = str(doc.get("buyer_account", ""))
        if self.riesgo.is_blocked(buyer):
            raise PermissionError(
                "cuenta bloqueada por proteccion: " + buyer
            )
        if source == "auction":
            self.commerce.persist_winner(
                listing_id=str(doc.get("listing_id", ""))
            )
        order = self.commerce.create_order(
            order_id=_nid("ORD-"),
            listing_id=str(doc.get("listing_id", "")),
            buyer_account=buyer,
            source=source,
        )
        self._send_json(201, {"ok": True, "data": order})
    def _order_action(self, order_id, action) -> None:
        doc = self._read_json() or {}
        if action == "pay":
            order = self.commerce.pay_order(
                order_id=order_id,
                provider=str(doc.get("provider", "wallet")),
            )
            self._send_json(200, {"ok": True, "data": order})
            return
        if action == "settle":
            order = self.commerce.settle_order(order_id=order_id)
            self._send_json(200, {"ok": True, "data": order})
            return
        if action == "ship":
            self.commerce.create_shipment(
                shipment_id=_nid("SHP-"),
                order_id=order_id,
                carrier=str(doc.get("carrier", "zyra-express")),
                origin=str(doc.get("origin", "SV")),
                destination=str(doc.get("destination", "SV")),
            )
            self._send_json(200, {"ok": True, "data": self.commerce.get_order(order_id)})
            return
        self._send_json(400, {"ok": False, "error": "unknown order action: %s" % action})

    def _shipment_action(self, shipment_id, action) -> None:
        doc = self._read_json() or {}
        if action == "track":
            shipment = self.commerce.add_tracking(
                shipment_id=shipment_id,
                status=str(doc.get("status", "in_transit")),
                location=str(doc.get("location", "")),
                description=str(doc.get("description", "")),
            )
            self._send_json(200, {"ok": True, "data": shipment})
            return
        if action == "deliver":
            shipment = self.commerce.confirm_delivery(shipment_id=shipment_id)
            self._send_json(200, {"ok": True, "data": shipment})
            return
        self._send_json(400, {"ok": False, "error": "unknown shipment action: %s" % action})

    def _mutual_reputation_json(self) -> None:
        doc = self._read_json()
        if doc is None:
            self._send_json(400, {"ok": False, "error": "invalid JSON"})
            return
        order_id = str(doc.get("order_id", ""))
        buyer_account = str(doc.get("buyer_account", ""))
        seller_account = str(doc.get("seller_account", ""))
        evidence = str(doc.get("evidence", "") or "transaccion completada en ZYRA MARKET")
        order = self.commerce.get_order(order_id)
        seller_zid = self._ensure_trusted_zid(seller_account)
        buyer_zid = self._ensure_trusted_zid(buyer_account)
        evidence_b64 = _b64.b64encode(evidence.encode("utf-8")).decode("ascii")

        def _net(path, payload):
            try:
                ok, data, err = self.net_client.post(path, payload)
                return (bool(ok), str(err or ""))
            except Exception as exc:
                return (False, str(exc))

        rep_b2s, err_b2s = _net(
            "/reputation/record",
            {"subject_zid": seller_zid, "actor_zid": buyer_zid, "kind": "positive", "evidence_b64": evidence_b64},
        )
        rep_s2b, err_s2b = _net(
            "/reputation/record",
            {"subject_zid": buyer_zid, "actor_zid": seller_zid, "kind": "positive", "evidence_b64": evidence_b64},
        )
        self.commerce.record_rep_event(
            order_id=order_id, subject_zid=seller_zid, actor_zid=buyer_zid,
            kind="positive", evidence=evidence, network_recorded=rep_b2s,
        )
        self.commerce.record_rep_event(
            order_id=order_id, subject_zid=buyer_zid, actor_zid=seller_zid,
            kind="positive", evidence=evidence, network_recorded=rep_s2b,
        )
        hist_s, err_hs = _net(
            "/history/append",
            {"zid": seller_zid, "entry_type": "asset", "actor_app": "subastas",
             "payload": {"event": "venta completada", "detail": "orden %s" % order_id}},
        )
        hist_b, err_hb = _net(
            "/history/append",
            {"zid": buyer_zid, "entry_type": "asset", "actor_app": "subastas",
             "payload": {"event": "compra completada", "detail": "orden %s" % order_id}},
        )
        self._send_json(
            200,
            {
                "ok": True,
                "data": {
                    "order_id": order_id,
                    "buyer_to_seller_network": rep_b2s,
                    "seller_to_buyer_network": rep_s2b,
                    "history_seller_recorded": hist_s,
                    "history_buyer_recorded": hist_b,
                    "errors": {
                        "rep_b2s": err_b2s,
                        "rep_s2b": err_s2b,
                        "hist_s": err_hs,
                        "hist_b": err_hb,
                    },
                },
            },
        )

    def _radar_scan_json(self) -> None:
        doc = self._read_json()
        if doc is None:
            self._send_json(400, {"ok": False, "error": "invalid JSON"})
            return
        purchase = float(doc.get("purchase_price", 0))
        sale = float(doc.get("estimated_sale_price", 0))
        if purchase <= 0 or sale <= 0:
            raise ValueError("purchase_price and estimated_sale_price must be positive")
        opportunity = self.commerce.create_opportunity(
            opportunity_id=_nid("OPP-"),
            title=str(doc.get("title", "oportunidad")),
            category=str(doc.get("category", "general")),
            purchase_price=purchase,
            shipping_cost=float(doc.get("shipping_cost", 0)),
            fees=float(doc.get("fees", 0)),
            estimated_sale_price=sale,
            demand_score=float(doc.get("demand_score", 0.5)),
            risk_score=float(doc.get("risk_score", 0.5)),
        )
        self._send_json(201, {"ok": True, "data": opportunity})

    def _style(self) -> str:
        return "".join([
            "<style>",
            "body{font-family:system-ui,sans-serif;background:#0d1117;color:#e6edf3;margin:0;padding:20px}",
            ".wrap{max-width:900px;margin:0 auto}",
            ".card{background:#161b22;border:1px solid #30363d;border-radius:12px;padding:14px;margin:10px 0}",
            "input,select,textarea{background:#0d1117;color:#e6edf3;border:1px solid #30363d;border-radius:8px;padding:8px;width:100%;margin:4px 0}",
            "button{background:#238636;color:#fff;border:none;border-radius:8px;padding:10px 16px;cursor:pointer;margin-top:6px}",
            "a{color:#58a6ff}",
            "code{background:#0d1117;padding:2px 6px;border-radius:6px}",
            "#msg{margin-top:8px;color:#8b949e;white-space:pre-wrap}",
            "</style>",
        ])

    def _nav_html(self) -> str:
        links = (
            ("/subastas/menu", "Menu"),
            ("/subastas/listings", "Publicaciones"),
            ("/subastas/vendedor", "Vendedor"),
            ("/subastas/comprador", "Comprador"),
            ("/subastas/operaciones", "Ordenes y envios"),
            ("/subastas/tienda", "Tiendas"),
            ("/subastas/dashboard", "Dashboard"),
            ("/subastas/mi-inscripcion", "Mi Inscripcion"),
            ("/subastas/inscripcion", "Inscripcion"),
            ("/subastas/gobierno-kyb", "KYB"),
            ("/subastas/gobierno", "Gobierno"),
            ("/subastas/proteccion", "Proteccion"),
            ("/subastas/riesgo", "Riesgo"),
            ("/subastas/fraude", "Fraude"),
            ("/subastas/revision", "Revision"),
        )
        parts = [
            "<nav style='background:#161b22;border:1px solid #30363d;border-radius:10px;"
            "padding:8px;margin:12px 0;display:flex;flex-wrap:wrap;gap:8px'>",
        ]
        for href, label in links:
            parts.append(
                "<a href='%s' style='color:#e6edf3;text-decoration:none;padding:6px 10px;"
                "background:#0d1117;border:1px solid #30363d;border-radius:8px'>%s</a>"
                % (href, label)
            )
        parts.append("</nav>")
        return "".join(parts)

    def _page_wrap(self, title, body) -> str:
        return "".join([
            "<html><head><meta charset='utf-8'>",
            "<meta name='viewport' content='width=device-width, initial-scale=1'>",
            "<title>%s</title>" % title,
            self._style(),
            "</head><body><div class='wrap'>",
            "<h1>ZYRA MARKET</h1>",
            self._nav_html(),
            body,
            "</div></body></html>",
        ])

    def _page_menu(self) -> str:
        body = "".join([
            "<p>El super mercado de la Red ZYRA. Elige tu area:</p>",
            "<div class='card'><h2>Soy vendedor</h2><p>Publicar, subastar y cerrar ventas.</p>"
            "<a href='/subastas/vendedor'><button>Entrar</button></a></div>",
            "<div class='card'><h2>Soy comprador</h2><p>Ofertar en subastas o comprar directo.</p>"
            "<a href='/subastas/comprador'><button>Entrar</button></a></div>",
            "<div class='card'><h2>Mis operaciones</h2><p>Pagar, enviar, rastrear y calificar.</p>"
            "<a href='/subastas/operaciones'><button>Entrar</button></a></div>",
            "<div class='card'><h2>Gobierno</h2><p>Resumen general y radar de oportunidades.</p>"
            "<a href='/subastas/gobierno'><button>Entrar</button></a></div>",
            "<div class='card'><h2>Registrarme</h2><p>Crea tu identidad biometrica (por ley).</p>"
            "<a href='/'><button>Ir al registro</button></a></div>",
        ])
        return self._page_wrap("ZYRA MARKET - Menu", body)

    def _page_vendedor(self) -> str:
        body = "".join([
            "<div class='card'><h2>Publicar / crear subasta</h2>",
            "<p>Tu publicacion queda sellada en la Red (evidencia inmutable).</p>",
            "<form method='POST' action='/subastas/listing'>",
            "<input name='seller_account' placeholder='Tu cuenta' required>",
            "<input name='title' placeholder='Titulo' required>",
            "<textarea name='description' placeholder='Descripcion' rows='3'></textarea>",
            "<input name='base_price' type='number' step='0.01' min='0.01' placeholder='Precio base' required>",
            "<button>Publicar y sellar</button>",
            "</form></div>",
            "<div class='card'><h2>Cerrar subasta (declarar ganador)</h2>",
            "<form method='POST' action='/subastas/close'>",
            "<input name='listing_id' placeholder='ID de publicacion' required>",
            "<input name='seller_account' placeholder='Tu cuenta' required>",
            "<button>Cerrar subasta</button>",
            "</form></div>",
            "<p><a href='/subastas/listings'>Ver publicaciones abiertas</a></p>",
        ])
        return self._page_wrap("ZYRA MARKET - Vendedor", body)

    def _page_comprador(self) -> str:
        body = "".join([
            "<div class='card'><h2>Ofertar en una subasta</h2>",
            "<p>Tu oferta debe superar el precio base y la mejor oferta actual.</p>",
            "<input id='bidListing' placeholder='ID de publicacion'>",
            "<input id='bidAccount' placeholder='Tu cuenta'>",
            "<input id='bidAmount' type='number' step='0.01' min='0.01' placeholder='Monto'>",
            "<button id='btnBid'>Enviar oferta</button>",
            "</div>",
            "<div class='card'><h2>Compra directa</h2>",
            "<input id='ordListing' placeholder='ID de publicacion'>",
            "<input id='ordAccount' placeholder='Tu cuenta'>",
            "<select id='ordSource'>",
            "<option value='direct'>Compra directa</option>",
            "<option value='auction'>Fui ganador de subasta</option>",
            "</select>",
            "<button id='btnOrder'>Crear orden</button>",
            "</div>",
            "<p id='msg'></p>",
            "<p><a href='/subastas/listings'>Ver publicaciones abiertas</a></p>",
            "<script>",
            "function v(id){return document.getElementById(id).value;}",
            "function msg(t){document.getElementById('msg').textContent=t;}",
            "function post(path,payload,okMsg){",
            "fetch(path,{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify(payload)})",
            ".then(function(r){return r.json();})",
            ".then(function(d){msg(d.ok?(okMsg+JSON.stringify(d.data||d.bid||d)):'Error: '+(d.error||''));})",
            ".catch(function(e){msg('Error: '+e);});}",
            "document.getElementById('btnBid').addEventListener('click',function(){",
            "post('/subastas/api/bids',{listing_id:v('bidListing'),bidder_account:v('bidAccount'),amount:parseFloat(v('bidAmount'))},'Oferta registrada: ');});",
            "document.getElementById('btnOrder').addEventListener('click',function(){",
            "post('/subastas/api/orders',{listing_id:v('ordListing'),buyer_account:v('ordAccount'),source:v('ordSource')},'Orden creada: ');});",
            "</script>",
        ])
        return self._page_wrap("ZYRA MARKET - Comprador", body)

    def _page_operaciones(self) -> str:
        body = "".join([
            "<div class='card'><h2>Ver orden</h2>",
            "<input id='qOrder' placeholder='ID de orden (ORD-...)'>",
            "<button id='btnQOrder'>Ver orden</button>",
            "</div>",
            "<div class='card'><h2>Pagar / liquidar orden</h2>",
            "<input id='actOrder' placeholder='ID de orden'>",
            "<select id='payProvider'>",
            "<option value='wallet'>cartera</option>",
            "<option value='cash'>efectivo</option>",
            "<option value='card'>tarjeta</option>",
            "</select>",
            "<button id='btnPay'>Pagar</button>",
            "<button id='btnSettle'>Liquidar</button>",
            "</div>",
            "<div class='card'><h2>Enviar (crear envio)</h2>",
            "<input id='shipOrder' placeholder='ID de orden'>",
            "<input id='shipCarrier' placeholder='Transportista'>",
            "<input id='shipOrigin' placeholder='Origen'>",
            "<input id='shipDest' placeholder='Destino'>",
            "<button id='btnShip'>Crear envio</button>",
            "</div>",
            "<div class='card'><h2>Rastrear / entregar envio</h2>",
            "<input id='trkShipment' placeholder='ID de envio (SHP-...)'>",
            "<select id='trkStatus'>",
            "<option value='picked_up'>recolectado</option>",
            "<option value='in_transit'>en transito</option>",
            "<option value='customs'>en aduana</option>",
            "<option value='out_for_delivery'>en reparto</option>",
            "</select>",
            "<input id='trkLocation' placeholder='Ubicacion'>",
            "<input id='trkDesc' placeholder='Descripcion'>",
            "<button id='btnTrack'>Registrar tracking</button>",
            "<button id='btnDeliver'>Confirmar entrega</button>",
            "</div>",
            "<div class='card'><h2>Reputacion mutua (calificar)</h2>",
            "<input id='repOrder' placeholder='ID de orden'>",
            "<input id='repBuyer' placeholder='Cuenta del comprador'>",
            "<input id='repSeller' placeholder='Cuenta del vendedor'>",
            "<input id='repEvidence' placeholder='Comentario (evidencia)'>",
            "<button id='btnRep'>Calificar a ambos</button>",
            "</div>",
            "<div class='card'><h2>Radar: registrar oportunidad</h2>",
            "<input id='radTitle' placeholder='Titulo'>",
            "<input id='radCategory' placeholder='Categoria'>",
            "<input id='radBuy' type='number' step='0.01' placeholder='Precio de compra'>",
            "<input id='radShip' type='number' step='0.01' placeholder='Costo envio'>",
            "<input id='radFees' type='number' step='0.01' placeholder='Fees/comisiones'>",
            "<input id='radSale' type='number' step='0.01' placeholder='Precio de venta estimado'>",
            "<input id='radDemand' type='number' step='0.05' min='0' max='1' placeholder='Demanda 0-1'>",
            "<input id='radRisk' type='number' step='0.05' min='0' max='1' placeholder='Riesgo 0-1'>",
            "<button id='btnRadar'>Registrar en radar</button>",
            "</div>",
            "<p id='msg'></p>",
            "<script>",
            "function v(id){return document.getElementById(id).value;}",
            "function msg(t){document.getElementById('msg').textContent=t;}",
            "function post(path,payload,prefix){",
            "fetch(path,{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify(payload)})",
            ".then(function(r){return r.json();})",
            ".then(function(d){msg(d.ok?(prefix+JSON.stringify(d.data||d)):'Error: '+(d.error||''));})",
            ".catch(function(e){msg('Error: '+e);});}",
            "function num(id){var x=parseFloat(v(id));return isNaN(x)?0:x;}",
            "document.getElementById('btnQOrder').addEventListener('click',function(){",
            "location.href='/subastas/order/'+v('qOrder');});",
            "document.getElementById('btnPay').addEventListener('click',function(){",
            "post('/subastas/api/orders/'+v('actOrder')+'/pay',{provider:v('payProvider')},'Pagada: ');});",
            "document.getElementById('btnSettle').addEventListener('click',function(){",
            "post('/subastas/api/orders/'+v('actOrder')+'/settle',{},'Liquidada: ');});",
            "document.getElementById('btnShip').addEventListener('click',function(){",
            "post('/subastas/api/orders/'+v('shipOrder')+'/ship',{carrier:v('shipCarrier'),origin:v('shipOrigin'),destination:v('shipDest')},'Envio creado: ');});",
            "document.getElementById('btnTrack').addEventListener('click',function(){",
            "post('/subastas/api/shipments/'+v('trkShipment')+'/track',{status:v('trkStatus'),location:v('trkLocation'),description:v('trkDesc')},'Tracking: ');});",
            "document.getElementById('btnDeliver').addEventListener('click',function(){",
            "post('/subastas/api/shipments/'+v('trkShipment')+'/deliver',{},'Entregado: ');});",
            "document.getElementById('btnRep').addEventListener('click',function(){",
            "post('/subastas/api/reputation/mutual',{order_id:v('repOrder'),buyer_account:v('repBuyer'),seller_account:v('repSeller'),evidence:v('repEvidence')},'Reputacion: ');});",
            "document.getElementById('btnRadar').addEventListener('click',function(){",
            "post('/subastas/api/radar/scan',{title:v('radTitle'),category:v('radCategory'),purchase_price:num('radBuy'),shipping_cost:num('radShip'),fees:num('radFees'),estimated_sale_price:num('radSale'),demand_score:num('radDemand'),risk_score:num('radRisk')},'Oportunidad: ');});",
            "</script>",
        ])
        return self._page_wrap("ZYRA MARKET - Operaciones", body)

    def _page_gobierno(self) -> str:
        s1 = self.store.summary()
        s2 = self.commerce.summary()
        opps = self.commerce.list_opportunities()
        rows = []
        for o in opps:
            buy = format(float(o.get("purchase_price") or 0), ".2f")
            sale = format(float(o.get("estimated_sale_price") or 0), ".2f")
            title = str(o.get("title", "?"))
            rows.append("<p>- <b>%s</b> compra %s venta est %s</p>" % (title, buy, sale))
        if not rows:
            rows.append("<p>Sin oportunidades registradas.</p>")
        body = "".join([
            "<div class='card'><h2>Resumen del mercado</h2>",
            "<p>Publicaciones totales: %s</p>" % str(s1.get("listings_total", 0)),
            "<p>Abiertas: %s</p>" % str(s1.get("open_listings", 0)),
            "<p>Cuentas: %s</p>" % str(s1.get("accounts", 0)),
            "<p>Ofertas: %s</p>" % str(s1.get("bids", 0)),
            "<p>Ordenes: %s</p>" % str(s2.get("orders_total", 0)),
            "<p>Entregadas: %s</p>" % str(s2.get("orders_delivered", 0)),
            "</div>",
            "<div class='card'><h2>Radar oportunidades: %s</h2>" % str(len(opps)),
            "".join(rows),
            "</div>",
        ])
        return self._page_wrap("ZYRA MARKET - Gobierno", body)

    def _order_html(self, order_id: str) -> str:
        try:
            order = self.commerce.get_order(order_id)
        except Exception:
            order = None
        if not order:
            body = "<p>No existe la orden: <code>%s</code></p>" % order_id
            return self._page_wrap("Orden no encontrada", body)
        rows = []
        for k, val in order.items():
            rows.append("<p><b>%s</b>: %s</p>" % (str(k), str(val)))
        body = "".join([
            "<div class='card'><h2>Orden %s</h2>" % order_id,
            "".join(rows),
            "</div>",
        ])
        return self._page_wrap("ZYRA MARKET - Orden", body)

    def _revision_html(self) -> str:
        summary = self.commerce.summary()
        return "".join([
            "<html><body><h1>Revision ZYRA MARKET</h1>",
            "<p>ordenes: %s</p>" % str(summary["orders_total"]),
            "<p>entregadas: %s</p>" % str(summary["orders_delivered"]),
            "<p>oportunidades radar: %s</p>" % str(summary["opportunities"]),
            "<a href='/subastas/menu'>Menu</a>",
            "</body></html>",
        ])

    def _home(self) -> str:
        return "".join([
            "<html><head><meta charset='utf-8'>",
            "<title>ZYRA MARKET</title>",
            self._style(),
            "</head><body><div class='wrap'>",
            "<h1>ZYRA MARKET</h1>",
            self._nav_html(),
            "<div class='card'><h2>Registrarme con biometria (por ley)</h2>",
            "<form id='bioReg' method='POST' action='/subastas/register'>",
            "<p>Nombre completo: <input name='name' required></p>",
            "<fieldset><legend>1) Foto del documento</legend>",
            "<input type='file' id='bioDoc' accept='image/*' capture='environment'></fieldset>",
            "<fieldset><legend>2) Selfie en vivo</legend>",
            "<input type='file' id='bioSlf' accept='image/*' capture='user'></fieldset>",
            "<input type='hidden' name='doc_image_b64' id='bioDocB64'>",
            "<input type='hidden' name='selfie_image_b64' id='bioSlfB64'>",
            "<p id='bioSt'>Estado: pendiente</p>",
            "<button type='submit'>Registrarme</button>",
            "</form>",
            "<canvas id='bioCv' style='display:none'></canvas>",
            "<script>",
            "(function(){",
            "var d=document.getElementById('bioDoc'),s=document.getElementById('bioSlf'),st=document.getElementById('bioSt'),hd=document.getElementById('bioDocB64'),hs=document.getElementById('bioSlfB64'),cv=document.getElementById('bioCv'),cx=cv.getContext('2d');",
            "function p(f,h){if(!f){return;}var r=new FileReader();r.onload=function(){var i=new Image();i.onload=function(){var k=Math.min(1,800/Math.max(i.width,i.height));cv.width=Math.round(i.width*k);cv.height=Math.round(i.height*k);cx.drawImage(i,0,0,cv.width,cv.height);h.value=cv.toDataURL('image/jpeg',0.72).split(',')[1];u();};i.src=r.result;};r.readAsDataURL(f);}",
            "function u(){st.textContent='Doc: '+(hd.value?'OK':'falta')+' | Selfie: '+(hs.value?'OK':'falta');}",
            "d.addEventListener('change',function(){p(d.files[0],hd);});",
            "s.addEventListener('change',function(){p(s.files[0],hs);});",
            "document.getElementById('bioReg').addEventListener('submit',function(e){if(!hd.value||!hs.value){e.preventDefault();st.textContent='Falta foto del documento o selfie.';}});",
            "})();",
            "</script>",
            "</div>",
            "<div class='card'><h2>ZYRA MARKET</h2>",
            "<p>El super mercado de la Red ZYRA.</p>",
            "<p>Roles: vendedor | comprador | gobierno</p>",
            "<a href='/subastas/menu'><button>Ir al Menu</button></a>",
            "</div>",
            "</div></body></html>",
        ])

    def _listings_html(self) -> str:
        rows_data = self.store.list_open()
        cards = []
        for row in rows_data:
            cards.append("".join([
                "<div class='card'>",
                "<b>%s</b>" % str(row["title"]),
                "<p>%s</p>" % str(row["description"]),
                "<p>Precio base: $%s</p>" % format(float(row["base_price"]), ".2f"),
                "<p>ID: <code>%s</code></p>" % str(row["listing_id"]),
                "<p><a href='/subastas/comprador'>Ofertar o comprar</a></p>",
                "</div>",
            ]))
        if not cards:
            cards.append(
                "<p>No hay publicaciones abiertas. "
                "<a href='/subastas/vendedor'>Crea la primera</a>.</p>"
            )
        return "".join([
            "<html><head><meta charset='utf-8'>",
            "<meta name='viewport' content='width=device-width, initial-scale=1'>",
            "<title>ZYRA MARKET</title>",
            self._style(),
            "</head><body><div class='wrap'>",
            "<h1>ZYRA MARKET</h1>",
            self._nav_html(),
            "<h2>Publicaciones abiertas</h2>",
            "".join(cards),
            "</div></body></html>",
        ])


def serve_subastas(store, client, *, host="127.0.0.1", port=0):
    _riesgo_inst = RiesgoStore(store._db, store._clock)
    _iext_inst = InscripcionesExt(store._db, store._clock, client)
    _eje_inst = EjecutivoStore(store._db, store._clock)
    _tdr_inst = TiendasStore(store._db, store._clock)
    handler = type(
        "BoundSubastasHandler",
        (SubastasApiHandler,),
        {
            "store": store,
            "net_client": client,
            "commerce": CommerceStore(store._db, store._clock),
            "tdr": _tdr_inst,
            "market_tiendas_page": market_tiendas_page,
            "market_gov_tiendas_page": market_gov_tiendas_page,
            "market_tiendas_api": market_tiendas_api,
            "market_gov_tiendas_api": market_gov_tiendas_api,
            "eje": _eje_inst,
            "market_dashboard_page": market_dashboard_page,
            "market_dashboard_api": market_dashboard_api,
            "iext": _iext_inst,
            "market_ins_ext_page": market_ins_ext_page,
            "market_gov_inscripcion_page": market_gov_inscripcion_page,
            "market_entity_register": market_entity_register,
            "market_doc_submit": market_doc_submit,
            "market_pm_add": market_pm_add,
            "market_verify_entity": market_verify_entity,
            "market_verify_document": market_verify_document,
            "disputes": _riesgo_inst,
            "riesgo": _riesgo_inst,
            "market_riesgo_page": market_riesgo_page,
            "market_riesgo_scan": market_riesgo_scan,
            "market_riesgo_block": market_riesgo_block,
            "accounts": AccountsStore(store._db, store._clock),
            "market_inscripcion_page": market_inscripcion_page,
            "market_login": market_login,
            "market_logout": market_logout,
            "market_register_user": market_register_user,
            "market_update_profile": market_update_profile,
            "market_link_zid": market_link_zid,
            "market_register_company": market_register_company,
            "market_gobierno_page": market_gobierno_page,
            "market_verify_company": market_verify_company,
            "_sess_user": _sess_user,
            "_require_role": _require_role,
            "market_disputes_page": market_disputes_page,
            "market_fraud_page": market_fraud_page,
            "market_dispute_detail": market_dispute_detail,
            "market_dispute_open": market_dispute_open,
            "market_dispute_action": market_dispute_action,
            "market_fraud_flag": market_fraud_flag,
        },
    )
    server = ThreadingHTTPServer((host, port), handler)
    server.bound_port = server.server_address[1]
    return server
