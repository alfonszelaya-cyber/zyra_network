"""SUBASTAS HTTP server (form route seals)."""
from __future__ import annotations

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
import base64 as _b64


def _find_value(doc, keys):
    if isinstance(doc, dict):
        for k, v in doc.items():
            if str(k).lower() in keys:
                return v
        for v in doc.values():
            found = _find_value(
                v, keys
            )
            if found is not None:
                return found
    elif isinstance(doc, list):
        for item in doc:
            found = _find_value(
                item, keys
            )
            if found is not None:
                return found
    return None


class SubastasApiHandler(BaseHTTPRequestHandler):
    store: SubastasStore
    net_client: object

    def log_message(
        self, format: str, *args,
    ) -> None:
        pass

    def _send_bytes(
        self,
        status: int,
        ctype: str,
        body: bytes,
    ) -> None:
        self.send_response(status)
        self.send_header(
            "Content-Type", ctype
        )
        self.send_header(
            "Content-Length",
            str(len(body)),
        )
        self.end_headers()
        self.wfile.write(body)

    def _send_html(
        self, status: int, html: str,
    ) -> None:
        self._send_bytes(
            status,
            "text/html",
            html.encode("utf-8"),
        )

    def _send_json(
        self, status: int, doc: dict,
    ) -> None:
        self._send_bytes(
            status,
            "application/json",
            json.dumps(doc).encode(
                "utf-8"
            ),
        )

    def _read_body(self) -> bytes:
        try:
            length = int(
                self.headers.get(
                    "Content-Length",
                    "0",
                )
                or "0"
            )
        except Exception:
            length = 0
        if length <= 0:
            return b""
        return self.rfile.read(length)

    def _read_form(self) -> dict:
        raw = self._read_body()
        parsed = parse_qs(
            raw.decode("utf-8")
        )
        form: dict[str, str] = {}
        for key, values in (
            parsed.items()
        ):
            if values:
                form[key] = values[0]
        return form

    def _read_json(self) -> dict | None:
        raw = self._read_body()
        if not raw:
            return {}
        try:
            doc = json.loads(
                raw.decode("utf-8")
            )
        except Exception:
            return None
        if not isinstance(doc, dict):
            return None
        return doc

    @staticmethod
    def _form_value(
        form: dict, key: str,
    ) -> str:
        value = form.get(key, "")
        if value is None:
            return ""
        return str(value)

    def _seal_listing(
        self,
        seller: str,
        title: str,
        description: str,
        base_price: float,
    ) -> str:
        content = "|".join(
            (
                seller,
                title,
                description,
                format(
                    base_price, ".2f"
                ),
            )
        )
        digest = hashlib.sha256(
            content.encode("utf-8")
        ).hexdigest()
        candidates = (
            {
                "title": title,
                "sha256": digest,
                "kind": "listing",
            },
            {
                "title": title,
                "content_sha256": (
                    digest
                ),
                "kind": "listing",
            },
            {"sha256": digest},
            {"content": content},
        )
        for payload in candidates:
            ok, data, _err = (
                self.net_client.post(
                    "/documents/seal",
                    payload,
                )
            )
            if ok and data:
                doc_id = _find_value(
                    data,
                    (
                        "document_id",
                        "seal_id",
                    ),
                )
                if isinstance(
                    doc_id, str
                ) and doc_id:
                    return doc_id
        return "DOC-" + digest[:16]

    def do_GET(self) -> None:
        path = self.path.split("?")[0]
        try:
            if path in (
                "/",
                "/subastas",
                "/subastas/",
            ):
                self._send_html(
                    200,
                    self._home(),
                )
                return
            if path in (
                "/subastas/api/health",
                "/subastas/health",
            ):
                self._send_json(
                    200,
                    {
                        "ok": True,
                        "app":
                        "subastas",
                    },
                )
                return
            if path == (
                "/subastas/listings"
            ):
                self._send_html(
                    200,
                    self._listings_html(),
                )
                return
            if path.startswith("/subastas/api/listings/"):
                listing = self.commerce.get_listing_full(
                    path[len("/subastas/api/listings/"):]
                )
                if listing is None:
                    self._send_json(
                        200,
                        {"ok": False, "error": "unknown listing"},
                    )
                    return
                self._send_json(200, {"ok": True, "data": listing})
                return
            if path == "/subastas/api/opportunities":
                self._send_json(
                    200,
                    {
                        "ok": True,
                        "data": {
                            "opportunities": self.commerce.list_opportunities()
                        },
                    },
                )
                return
            if path == "/subastas/revision":
                self._send_html(200, self._revision_html())
                return
            if path.startswith("/subastas/api/orders/"):
                self._send_json(
                    200,
                    {"ok": True, "data": self.commerce.get_order(
                        path[len("/subastas/api/orders/"):]
                    )},
                )
                return
            if path.startswith("/subastas/api/shipments/"):
                self._send_json(
                    200,
                    {"ok": True, "data": self.commerce.get_shipment(
                        path[len("/subastas/api/shipments/"):]
                    )},
                )
                return
            if path == (
                "/subastas/api/summary"
            ):
                self._send_json(
                    200,
                    {
                        "ok": True,
                        "summary": (
                            self.store
                            .summary()
                        ),
                    },
                )
                return
            self._send_json(
                404,
                {
                    "ok": False,
                    "error":
                    "unknown path: "
                    + path,
                },
            )
        except Exception:
            self._send_json(
                500,
                {
                    "ok": False,
                    "error":
                    "server error",
                },
            )

    def do_POST(self) -> None:
        path = self.path.split("?")[0]
        try:
            if path == (
                "/subastas/listing"
            ):
                self._create_listing_form()
                return
            if path == (
                "/subastas/api/bids"
            ):
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
                parts = path[len("/subastas/api/orders/"):].split("/")
                self._order_action(
                    parts[0],
                    parts[1] if len(parts) > 1 else "",
                )
                return
            if path.startswith("/subastas/api/shipments/"):
                parts = path[len("/subastas/api/shipments/"):].split("/")
                self._shipment_action(
                    parts[0],
                    parts[1] if len(parts) > 1 else "",
                )
                return
            if path == (
                "/subastas/close"
            ):
                self._close_form()
                return
            self._send_json(
                404,
                {
                    "ok": False,
                    "error":
                    "unknown path: "
                    + path,
                },
            )
        except (
            ValueError,
            LookupError,
            PermissionError,
        ) as exc:
            self._send_json(
                400,
                {
                    "ok": False,
                    "error": str(exc),
                },
            )
        except Exception:
            self._send_json(
                500,
                {
                    "ok": False,
                    "error":
                    "server error",
                },
            )

    def _create_listing_form(
        self,
    ) -> None:
        form = self._read_form()
        seller_account = (
            self._form_value(
                form, "seller_account"
            )
        )
        title = self._form_value(
            form, "title"
        )
        description = (
            self._form_value(
                form, "description"
            )
        )
        raw_price = (
            self._form_value(
                form, "base_price"
            )
        )
        if not seller_account or not title:
            self._send_html(
                400,
                "<html><body>"
                "<h1>Faltan datos"
                "</h1></body></html>",
            )
            return
        try:
            base_price = float(
                raw_price
            )
        except (TypeError, ValueError):
            self._send_html(
                400,
                "<html><body>"
                "<h1>Precio invalido"
                "</h1></body></html>",
            )
            return
        account = (
            self.store.get_account(
                seller_account
            )
        )
        seller_zid = (
            account["zid"]
            if account
            else None
        )
        document_id = (
            self._seal_listing(
                seller_account,
                title,
                description,
                base_price,
            )
        )
        listing_id = new_listing_id()
        self.store.add_listing(
            listing_id=listing_id,
            seller_account=(
                seller_account
            ),
            seller_zid=seller_zid,
            title=title,
            description=description,
            base_price=base_price,
            document_id=document_id,
        )
        html = (
            "<html><body>"
            "<h1>SUBASTAS</h1>"
            "<p>SELLADO</p>"
            "<p>listing: "
            + listing_id
            + "</p>"
            "<p>documento: "
            + document_id
            + "</p>"
            "</body></html>"
        )
        self._send_html(200, html)

    def _create_bid_json(self) -> None:
        doc = self._read_json()
        if doc is None:
            self._send_json(
                400,
                {
                    "ok": False,
                    "error":
                    "invalid JSON",
                },
            )
            return
        bid = self.store.place_bid(
            bid_id=new_bid_id(),
            listing_id=str(
                doc.get("listing_id", "")
            ),
            bidder_account=str(
                doc.get(
                    "bidder_account",
                    "",
                )
            ),
            amount=float(
                doc.get("amount", 0)
            ),
        )
        self._send_json(
            200,
            {
                "ok": True,
                "bid": bid,
            },
        )

    def _close_form(self) -> None:
        form = self._read_form()
        closed = (
            self.store.close_listing(
                listing_id=(
                    self._form_value(
                        form,
                        "listing_id",
                    )
                ),
                seller_account=(
                    self._form_value(
                        form,
                        "seller_account",
                    )
                ),
            )
        )
        html = (
            "<html><body>"
            "<h1>SUBASTAS</h1>"
            "<p>GANADOR: "
            + str(
                closed[
                    "winner_account"
                ]
            )
            + "</p>"
            "<p>PRECIO FINAL: "
            + format(
                closed["final_price"],
                ".2f",
            )
            + "</p>"
            "</body></html>"
        )
        self._send_html(200, html)

    def _ensure_trusted_zid(self, account_id: str) -> str:
        """Canonical identity + trust via net_client
        (the exact pattern proven by MPE and SEMILLA).
        Falls back to stored ZID only if network down."""
        ok, data, _err = self.net_client.post(
            "/identity/register",
            {
                "kind": "person",
                "display_name": account_id,
                "actor": "subastas",
            },
        )
        zid = None
        if ok and data:
            found = _find_value(data, ("zid",))
            if isinstance(found, str) and found.startswith("ZID-"):
                zid = found
        if zid is None:
            existing = self.commerce.account_zid(account_id)
            if existing:
                return existing
            raise ValueError(
                "no network ZID available for " + account_id
            )
        try:
            self.net_client.post(
                "/trust/complete",
                {"zid": zid, "actor": "subastas"},
            )
        except Exception:
            pass
        return zid

    def _create_order_json(self) -> None:
        doc = self._read_json()
        if doc is None:
            self._send_json(400, {"ok": False, "error": "invalid JSON"})
            return
        source = str(doc.get("source", "direct"))
        if source == "auction":
            self.commerce.persist_winner(
                listing_id=str(doc.get("listing_id", ""))
            )
        order = self.commerce.create_order(
            order_id=_nid("ORD-"),
            listing_id=str(doc.get("listing_id", "")),
            buyer_account=str(doc.get("buyer_account", "")),
            source=source,
        )
        self._send_json(201, {"ok": True, "data": order})

    def _order_action(self, order_id: str, action: str) -> None:
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
            self._send_json(
                200,
                {"ok": True, "data": self.commerce.get_order(order_id)},
            )
            return
        self._send_json(
            400,
            {"ok": False, "error": "unknown order action: " + action},
        )

    def _shipment_action(self, shipment_id: str, action: str) -> None:
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
            shipment = self.commerce.confirm_delivery(
                shipment_id=shipment_id,
            )
            self._send_json(200, {"ok": True, "data": shipment})
            return
        self._send_json(
            400,
            {"ok": False, "error": "unknown shipment action: " + action},
        )

    def _mutual_reputation_json(self) -> None:
        doc = self._read_json()
        if doc is None:
            self._send_json(400, {"ok": False, "error": "invalid JSON"})
            return
        order_id = str(doc.get("order_id", ""))
        buyer_account = str(doc.get("buyer_account", ""))
        seller_account = str(doc.get("seller_account", ""))
        evidence = str(
            doc.get("evidence", "")
            or "transaccion completada en SUBASTAS"
        )
        order = self.commerce.get_order(order_id)
        seller_zid = self._ensure_trusted_zid(seller_account)
        buyer_zid = self._ensure_trusted_zid(buyer_account)
        evidence_b64 = _b64.b64encode(
            evidence.encode("utf-8")
        ).decode("ascii")

        def _net(path: str, payload: dict) -> tuple:
            try:
                ok, data, err = self.net_client.post(
                    path, payload
                )
                return (bool(ok), str(err or ""))
            except Exception as exc:
                return (False, str(exc))

        rep_b2s, err_b2s = _net(
            "/reputation/record",
            {
                "subject_zid": seller_zid,
                "actor_zid": buyer_zid,
                "kind": "positive",
                "evidence_b64": evidence_b64,
            },
        )
        rep_s2b, err_s2b = _net(
            "/reputation/record",
            {
                "subject_zid": buyer_zid,
                "actor_zid": seller_zid,
                "kind": "positive",
                "evidence_b64": evidence_b64,
            },
        )
        self.commerce.record_rep_event(
            order_id=order_id,
            subject_zid=seller_zid,
            actor_zid=buyer_zid,
            kind="positive",
            evidence=evidence,
            network_recorded=rep_b2s,
        )
        self.commerce.record_rep_event(
            order_id=order_id,
            subject_zid=buyer_zid,
            actor_zid=seller_zid,
            kind="positive",
            evidence=evidence,
            network_recorded=rep_s2b,
        )
        hist_s, err_hs = _net(
            "/history/append",
            {
                "zid": seller_zid,
                "entry_type": "asset",
                "actor_app": "subastas",
                "payload": {
                    "event": "venta completada",
                    "detail": "orden " + order_id,
                },
            },
        )
        hist_b, err_hb = _net(
            "/history/append",
            {
                "zid": buyer_zid,
                "entry_type": "asset",
                "actor_app": "subastas",
                "payload": {
                    "event": "compra completada",
                    "detail": "orden " + order_id,
                },
            },
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
            raise ValueError(
                "purchase_price and estimated_sale_price must be positive"
            )
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

    def _revision_html(self) -> str:
        summary = self.commerce.summary()
        return (
            "<html><body><h1>Revision SUBASTAS</h1>"
            "<p>ordenes: " + str(summary["orders_total"]) + "</p>"
            "<p>entregadas: " + str(summary["orders_delivered"]) + "</p>"
            "<p>oportunidades radar: " + str(summary["opportunities"]) + "</p>"
            "<a href='/subastas'>Inicio</a>"
            "</body></html>"
        )

    def _home(self) -> str:
        return (
            "<html><head>"
            "<title>SUBASTAS</title>"
            "</head><body>"
            "<h1>SUBASTAS</h1>"
            "<p>Super-market ZYRA."
            "</p>"
            "<p>Roles: vendedor |"
            " comprador | gobierno</p>"
            "<ul>"
            "<li>POST"
            " /subastas/listing"
            " (form, sella)</li>"
            "<li>POST"
            " /subastas/api/bids"
            "</li>"
            "<li>POST"
            " /subastas/close</li>"
            "<li>GET"
            " /subastas/listings</li>"
            "<li>GET"
            " /subastas/api/health</li>"
            "</ul></body></html>"
        )

    def _listings_html(self) -> str:
        rows = self.store.list_open()
        html = (
            "<html><body><h1>"
            "Publicaciones abiertas"
            "</h1><ul>"
        )
        for row in rows:
            html += (
                "<li>"
                + str(
                    row["listing_id"]
                )
                + " - "
                + str(row["title"])
                + " - base "
                + format(
                    float(
                        row[
                            "base_price"
                        ]
                    ),
                    ".2f",
                )
                + "</li>"
            )
        html += (
            "</ul></body></html>"
        )
        return html


def serve_subastas(
    store: SubastasStore,
    client: object,
    *,
    host: str = "127.0.0.1",
    port: int = 0,
) -> ThreadingHTTPServer:
    handler = type(
        "BoundSubastasHandler",
        (SubastasApiHandler,),
        {
            "store": store,
            "net_client": client,
            "commerce": CommerceStore(
                store._db, store._clock
            ),
        },
    )
    server = ThreadingHTTPServer(
        (host, port), handler,
    )
    server.bound_port = (
        server.server_address[1]
    )
    return server
