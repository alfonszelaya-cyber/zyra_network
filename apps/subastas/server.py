"""SUBASTAS HTTP surface."""
from __future__ import annotations

import json
import uuid
from http.server import (
    BaseHTTPRequestHandler,
    ThreadingHTTPServer,
)
from typing import Any, ClassVar
from urllib.parse import urlparse

from apps.subastas.infrastructure.persistence.subastas_store import (
    SubastasStore,
)
from apps.subastas.infrastructure.network.network_client import (
    NetworkClient,
)
from apps.subastas.services.subastas_link import (
    SubastasLink,
)

_CSS = (
    "body{font-family:system-ui,sans-serif;"
    "background:#0d1117;color:#e6edf3;"
    "display:flex;justify-content:center;"
    "padding:20px;margin:0}"
    ".wrap{max-width:680px;width:100%}"
    "h1{font-size:1.3rem}"
    "h2{font-size:1rem;margin-top:20px;"
    "color:#58a6ff}"
    ".card{background:#161b22;border:1px solid"
    " #30363d;border-radius:10px;padding:14px;"
    "margin-top:10px}"
    "button{background:#238636;color:#fff;"
    "border:none;padding:12px 18px;border-radius:8px;"
    "font-size:1rem;cursor:pointer;margin:6px 4px"
    " 0 0;width:100%;text-align:left}"
    "button.gray{background:#30363d}"
    "input,select,textarea{width:100%;"
    "box-sizing:border-box;background:#0d1117;"
    "color:#e6edf3;border:1px solid #30363d;"
    "border-radius:6px;padding:8px;margin:4px 0;"
    "font-size:0.95rem}"
    ".ok{background:#0f2417;border:1px solid"
    " #238636;border-radius:8px;padding:10px;"
    "margin:8px 0}"
)


def _page(title: str, body: str) -> str:
    return (
        "<!DOCTYPE html><html lang='es'><head>"
        "<meta charset='utf-8'>"
        "<meta name='viewport' content='width="
        "device-width, initial-scale=1'>"
        f"<title>{title}</title>"
        f"<style>{_CSS}</style></head><body>"
        f"<div class='wrap'>{body}</div></body>"
        "</html>"
    )


class SubastasApiHandler(
    BaseHTTPRequestHandler
):
    store: ClassVar[SubastasStore]
    link: ClassVar[SubastasLink]

    def log_message(
        self, format: str, *args: object
    ) -> None:
        return None

    def do_GET(self) -> None:
        self._safe("GET")

    def do_POST(self) -> None:
        self._safe("POST")

    def _safe(self, method: str) -> None:
        try:
            self._route(method)
        except LookupError as exc:
            self._html(
                404,
                _page(
                    "No encontrado",
                    "<h1>404</h1>"
                    f"<p>{exc}</p>",
                ),
            )
        except ValueError as exc:
            self._html(
                400,
                _page(
                    "Error",
                    "<h1>Dato invalido"
                    f"</h1><p>{exc}</p>",
                ),
            )
        except Exception as exc:
            self._html(
                500,
                _page(
                    "Error",
                    "<h1>Error interno"
                    f"</h1><p>{exc}</p>",
                ),
            )

    def _route(self, method: str) -> None:
        path = urlparse(self.path).path
        segments = [
            s
            for s in path.split("/")
            if s
        ]
        if segments[:1] != ["subastas"]:
            self._html(
                404,
                _page(
                    "404",
                    "<h1>Fuera de"
                    " SUBASTAS</h1>",
                ),
            )
            return
        tail = segments[1:]
        if method == "GET":
            self._get(tail)
        else:
            self._post(tail)

    def _get(self, s: list[str]) -> None:
        if s[:1] == ["api"]:
            self._api_get(s[1:])
            return
        store = type(self).store
        if not s or s == ["home"]:
            self._home()
            return
        if s == ["listings"]:
            listings = store.list_open()
            items = ""
            for l in listings:
                items = (
                    items
                    + "<li>• "
                    + l["title"]
                    + " - base $"
                    + str(l["base_price"])
                    + " <small>("
                    + l["listing_id"]
                    + ")</small></li>"
                )
            if not items:
                items = (
                    "<li>Sin listados"
                    " abiertos</li>"
                )
            self._html(
                200,
                _page(
                    "SUBASTAS - Listados",
                    "<h1>Listados abiertos"
                    "</h1><ul>"
                    + items
                    + "</ul>"
                    "<a href='/subastas'>"
                    "<button class='gray'>"
                    "Inicio</button></a>",
                ),
            )
            return
        if s == ["summary"]:
            listings = store.list_open()
            self._send(
                200,
                {
                    "ok": True,
                    "data": {
                        "open_listings": len(
                            listings
                        ),
                    },
                },
            )
            return
        self._html(
            404,
            _page("404", "<h1>No"
            " encontrado</h1>"),
        )

    def _post(self, s: list[str]) -> None:
        if s[:1] == ["api"]:
            self._api_post(s[1:])
            return
        store = type(self).store
        link = type(self).link
        doc = self._read_form()
        if s == ["register"]:
            name = self._req(doc, "name")
            account_id = (
                "SBS-"
                + uuid.uuid4().hex[:12]
            )
            zid: str | None = None
            ok, data, _error = (
                link.register_account(name)
            )
            if ok and data is not None:
                zid = str(data.get("zid"))
            store.add_account(
                account_id=account_id,
                zid=zid,
                name=name,
            )
            zid_text = (
                zid
                if zid is not None
                else "pendiente de conexion"
            )
            self._html(
                200,
                _page(
                    "Cuenta creada",
                    "<h1>Cuenta creada"
                    "</h1>"
                    "<p>Tu ID: <b>"
                    + account_id
                    + "</b></p>"
                    "<p>Tu ZID: <b>"
                    + zid_text
                    + "</b></p>"
                    "<a href='/subastas'>"
                    "<button>Inicio"
                    "</button></a>",
                ),
            )
            return
        if s == ["listing"]:
            seller_account = self._req(
                doc, "seller_account"
            )
            seller = store.get_account(
                seller_account
            )
            title = self._req(
                doc, "title"
            )
            description = self._req(
                doc, "description"
            )
            base_price = float(
                doc.get("base_price", 0)
            )
            listing_id = (
                "LST-"
                + uuid.uuid4().hex[:10]
            )
            document_id: str | None = None
            zid = seller.get("zid")
            if zid is not None:
                ok, data, _error = (
                    link.seal_listing(
                        owner_zid=str(
                            zid
                        ),
                        listing_id=(
                            listing_id
                        ),
                        title=title,
                        description=(
                            description
                        ),
                    )
                )
                if (
                    ok
                    and data is not None
                ):
                    document_id = str(
                        data.get(
                            "document_id"
                        )
                    )
            row = store.add_listing(
                listing_id=listing_id,
                seller_account=(
                    seller_account
                ),
                seller_zid=(
                    str(zid)
                    if zid is not None
                    else None
                ),
                title=title,
                description=(
                    description
                ),
                base_price=base_price,
                document_id=document_id,
            )
            sealed_text = (
                "SELLADO en la Red"
                if document_id
                else "pendiente de sello"
            )
            self._html(
                200,
                _page(
                    "Listado publicado",
                    "<h1>Listado"
                    " publicado</h1>"
                    f"<p>{title} - base $"
                    + str(base_price)
                    + "</p><p>"
                    + sealed_text
                    + "</p><a href="
                    "'/subastas/listings'>"
                    "<button>Ver listados"
                    "</button></a>",
                ),
            )
            return
        if s == ["bid"]:
            listing_id = self._req(
                doc, "listing_id"
            )
            bidder_account = self._req(
                doc, "bidder_account"
            )
            amount = float(
                doc.get("amount", 0)
            )
            bid_id = (
                "BID-"
                + uuid.uuid4().hex[:10]
            )
            result = store.place_bid(
                bid_id=bid_id,
                listing_id=listing_id,
                bidder_account=(
                    bidder_account
                ),
                amount=amount,
            )
            self._html(
                200,
                _page(
                    "Puja registrada",
                    "<h1>Puja registrada"
                    "</h1><p>$"
                    + str(
                        result["amount"]
                    )
                    + "</p>"
                    "<a href='/subastas/"
                    "listings'>"
                    "<button>Ver listados"
                    "</button></a>",
                ),
            )
            return
        if s == ["close"]:
            listing_id = self._req(
                doc, "listing_id"
            )
            seller_account = self._req(
                doc, "seller_account"
            )
            row = store.close_listing(
                listing_id=listing_id,
                seller_account=(
                    seller_account
                ),
            )
            winner = row.get(
                "winner_account"
            )
            if winner is None:
                winner_text = (
                    "Sin pujas - quedo"
                    " sin venta"
                )
            else:
                winner_text = (
                    "Ganador: "
                    + str(winner)
                )
            self._html(
                200,
                _page(
                    "Subasta cerrada",
                    "<h1>Subasta cerrada"
                    "</h1><p>"
                    + winner_text
                    + "</p><a href="
                    "'/subastas/listings'>"
                    "<button>Ver listados"
                    "</button></a>",
                ),
            )
            return
        self._html(
            404,
            _page("404", "<h1>Ruta"
            " desconocida</h1>"),
        )

    def _read_form(
        self,
    ) -> dict[str, Any]:
        length_header = self.headers.get(
            "Content-Length"
        )
        if length_header is None:
            raise ValueError(
                "Content-Length required"
            )
        raw = self.rfile.read(
            int(length_header)
        ).decode("utf-8")
        doc: dict[str, Any] = {}
        for pair in raw.split("&"):
            if "=" in pair:
                key, value = pair.split(
                    "=", 1
                )
                doc[key] = value.replace(
                    "+", " "
                )
        return doc

    def _read_json(
        self,
    ) -> dict[str, Any]:
        length_header = self.headers.get(
            "Content-Length"
        )
        if length_header is None:
            raise ValueError(
                "Content-Length required"
            )
        raw = self.rfile.read(
            int(length_header)
        )
        parsed: Any = json.loads(
            raw.decode("utf-8")
        )
        if not isinstance(parsed, dict):
            raise ValueError(
                "body must be a JSON"
                " object"
            )
        return {
            str(k): v
            for k, v in parsed.items()
        }

    @staticmethod
    def _req(
        doc: dict[str, Any], key: str
    ) -> str:
        value: Any = doc.get(key)
        if isinstance(value, int) and not isinstance(
            value, bool
        ):
            value = str(value)
        if not isinstance(value, str):
            raise ValueError(
                f"missing field: {key}"
            )
        if not value.strip():
            raise ValueError(
                f"missing field: {key}"
            )
        return value

    def _api_get(self, s: list[str]) -> None:
        store = type(self).store
        if s == ["health"]:
            self._send(
                200,
                {
                    "ok": True,
                    "data": {
                        "app": "subastas",
                        "status":
                        "operational",
                    },
                },
            )
            return
        if s == ["listings"]:
            self._send(
                200,
                {
                    "ok": True,
                    "data": list(
                        store.list_open()
                    ),
                },
            )
            return
        self._send(
            404,
            {
                "ok": False,
                "error": {
                    "type": "not_found",
                    "message":
                    "unknown api route",
                },
            },
        )

    def _api_post(
        self, s: list[str]
    ) -> None:
        store = type(self).store
        doc = self._read_json()
        if s == ["accounts"]:
            account_id = (
                "SBS-"
                + uuid.uuid4().hex[:12]
            )
            row = store.add_account(
                account_id=account_id,
                zid=doc.get("zid"),
                name=self._req(doc, "name"),
            )
            self._send(
                201,
                {
                    "ok": True,
                    "data": row,
                },
            )
            return
        if s == ["listings"]:
            row = store.add_listing(
                listing_id=(
                    "LST-"
                    + uuid.uuid4().hex[:10]
                ),
                seller_account=self._req(
                    doc,
                    "seller_account",
                ),
                seller_zid=doc.get(
                    "seller_zid"
                ),
                title=self._req(
                    doc, "title"
                ),
                description=self._req(
                    doc, "description"
                ),
                base_price=float(
                    doc.get(
                        "base_price", 0
                    )
                ),
                document_id=None,
            )
            self._send(
                201,
                {
                    "ok": True,
                    "data": row,
                },
            )
            return
        self._send(
            404,
            {
                "ok": False,
                "error": {
                    "type": "not_found",
                    "message":
                    "unknown api route",
                },
            },
        )

    def _home(self) -> None:
        body = (
            "<h1>🔨 SUBASTAS</h1>"
            "<p>El mercado de ZYRA:"
            " cada listado sellado,"
            " cada reputacion con"
            " evidencia - nadie vende"
            " humo.</p>"
            "<h2>Crear cuenta</h2>"
            "<div class='card'>"
            "<form method='POST'"
            " action='/subastas/register'>"
            "<input name='name'"
            " placeholder='Mi nombre'>"
            "<button>Crear cuenta en la"
            " Red</button>"
            "</form></div>"
            "<h2>Comprar / pujar</h2>"
            "<div class='card'>"
            "<a href='/subastas/listings'>"
            "<button>Ver listados"
            " abiertos</button></a>"
            "</div>"
            "<h2>Vender (listado sellado"
            " en la Red)</h2>"
            "<div class='card'>"
            "<form method='POST'"
            " action='/subastas/listing'>"
            "<input name='seller_account'"
            " placeholder='Mi ID de cuenta"
            " (SBS-...)'>"
            "<input name='title'"
            " placeholder='Titulo del"
            " producto'>"
            "<input name='description'"
            " placeholder='Descripcion'>"
            "<input name='base_price'"
            " placeholder='Precio base'>"
            "<button>Publicar listado"
            "</button>"
            "</form></div>"
        )
        self._html(
            200, _page("SUBASTAS", body)
        )

    def _html(
        self, status: int, html: str
    ) -> None:
        body = html.encode("utf-8")
        self.send_response(status)
        self.send_header(
            "Content-Type",
            "text/html; charset=utf-8",
        )
        self.send_header(
            "Content-Length",
            str(len(body)),
        )
        self.end_headers()
        self.wfile.write(body)

    def _send(
        self,
        status: int,
        payload: dict[str, Any],
    ) -> None:
        body = json.dumps(payload).encode(
            "utf-8"
        )
        self.send_response(status)
        self.send_header(
            "Content-Type",
            "application/json",
        )
        self.send_header(
            "Content-Length",
            str(len(body)),
        )
        self.end_headers()
        self.wfile.write(body)


class SubastasServer(ThreadingHTTPServer):
    daemon_threads = True
    allow_reuse_address = True

    def __init__(
        self, address: tuple[str, int]
    ) -> None:
        super().__init__(
            address, SubastasApiHandler
        )

    @property
    def bound_port(self) -> int:
        return int(
            self.server_address[1]
        )


def serve_subastas(
    store: SubastasStore,
    client: NetworkClient,
    *,
    host: str = "127.0.0.1",
    port: int = 0,
) -> SubastasServer:
    SubastasApiHandler.store = store
    SubastasApiHandler.link = SubastasLink(
        client
    )
    return SubastasServer((host, port))
