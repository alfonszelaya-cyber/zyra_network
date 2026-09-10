"""NEXO HTTP surface: empresario + contador."""
from __future__ import annotations

import json
import uuid
from http.server import (
    BaseHTTPRequestHandler,
    ThreadingHTTPServer,
)
from typing import Any, ClassVar
from urllib.parse import urlparse

from apps.nexo.infrastructure.persistence.nexo_store import (
    KINDS,
    NexoStore,
)
from apps.nexo.infrastructure.network.network_client import (
    NetworkClient,
)
from apps.nexo.services.nexo_link import NexoLink

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
    "input,select{width:100%;box-sizing:border-box;"
    "background:#0d1117;color:#e6edf3;"
    "border:1px solid #30363d;border-radius:6px;"
    "padding:8px;margin:4px 0;font-size:0.95rem}"
    ".big{font-size:1.6rem;font-weight:bold;"
    "color:#58a6ff}"
    ".ok{background:#0f2417;border:1px solid"
    " #238636;border-radius:8px;padding:10px;"
    "margin:8px 0}"
    ".bad{background:#2d1216;border:1px solid"
    " #da3633;border-radius:8px;padding:10px;"
    "margin:8px 0}"
    "small{color:#8b949e}"
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


class NexoApiHandler(
    BaseHTTPRequestHandler
):
    store: ClassVar[NexoStore]
    link: ClassVar[NexoLink]

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
        if segments[:1] != ["nexo"]:
            self._html(
                404,
                _page(
                    "404",
                    "<h1>Fuera de NEXO"
                    "</h1>",
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
        if s[0] == "contador":
            summary = store.summary()
            if summary["chain_intact"]:
                chain = (
                    "<div class='ok'>✅"
                    " Cadena contable"
                    " INTACTA - nada fue"
                    " alterado</div>"
                )
            else:
                chain = (
                    "<div class='bad'>❌"
                    " CADENA ALTERADA"
                    " - hay registros"
                    " modificados</div>"
                )
            by_kind = summary["by_kind"]
            rows = ""
            for k, v in by_kind.items():
                rows = (
                    rows
                    + "<li>• "
                    + k
                    + ": "
                    + str(v["count"])
                    + " ops / $"
                    + str(v["total"])
                    + "</li>"
                )
            if not rows:
                rows = (
                    "<li>Sin operaciones"
                    "</li>"
                )
            body = (
                "<h1>📊 Panel Contador"
                "</h1>"
                "<p>Verificacion con"
                " evidencia criptografica"
                " de la Red.</p>"
                + chain
                + "<h2>Resumen</h2><ul>"
                + rows
                + "</ul>"
                "<a href='/nexo'>"
                "<button class='gray'>"
                "Inicio</button></a>"
            )
            self._html(
                200,
                _page(
                    "NEXO - Contador", body
                ),
            )
            return
        if s == ["ledger"]:
            ops = store.list_operations()
            items = ""
            for o in ops:
                items = (
                    items
                    + "<li>• #"
                    + str(o["seq"])
                    + " ["
                    + o["kind"]
                    + "] $"
                    + str(o["amount"])
                    + " hash: "
                    + o["entry_hash"][:12]
                    + "...</li>"
                )
            if not items:
                items = (
                    "<li>Libro vacio</li>"
                )
            self._html(
                200,
                _page(
                    "NEXO - Libro",
                    "<h1>Libro diario"
                    " (encadenado)</h1><ul>"
                    + items
                    + "</ul>"
                    "<a href='/nexo'>"
                    "<button class='gray'>"
                    "Inicio</button></a>",
                ),
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
            company_id = (
                "EMP-"
                + uuid.uuid4().hex[:12]
            )
            zid: str | None = None
            ok, data, _error = (
                link.register_company(
                    name
                )
            )
            if ok and data is not None:
                zid = str(data.get("zid"))
            store.add_company(
                company_id=company_id,
                zid=zid,
                name=name,
                synced=(
                    zid is not None
                ),
            )
            zid_text = (
                zid
                if zid is not None
                else "pendiente de conexion"
            )
            self._html(
                200,
                _page(
                    "Empresa registrada",
                    "<h1>Empresa en la"
                    " Red</h1>"
                    "<p>Tu ID: <b>"
                    + company_id
                    + "</b></p>"
                    "<p>Tu ZID: <b>"
                    + zid_text
                    + "</b></p>"
                    "<a href='/nexo'>"
                    "<button>Inicio"
                    "</button></a>",
                ),
            )
            return
        if s == ["operation"]:
            seller = self._req(
                doc, "seller_zid"
            )
            buyer = self._req(
                doc, "buyer_zid"
            )
            kind = self._req(doc, "kind")
            amount = float(
                doc.get("amount", 0)
            )
            if amount <= 0:
                raise ValueError(
                    "monto invalido"
                )
            description = self._req(
                doc, "description"
            )
            operation_id = (
                "OP-"
                + uuid.uuid4().hex[:12]
            )
            invoice_id: str | None = None
            synced = False
            ok, data, _error = (
                link.seal_invoice(
                    owner_zid=seller,
                    invoice_id=(
                        operation_id
                    ),
                    content=(
                        kind
                        + "|"
                        + seller
                        + "|"
                        + buyer
                        + "|"
                        + str(amount)
                        + "|"
                        + description
                    ).encode("utf-8"),
                )
            )
            if ok and data is not None:
                invoice_id = str(
                    data.get(
                        "document_id"
                    )
                )
                synced = True
            link.record_fiscal_event(
                seller,
                kind,
                operation_id
                + ": $"
                + str(amount),
            )
            row = store.record_operation(
                operation_id=(
                    operation_id
                ),
                kind=kind,
                seller_zid=seller,
                buyer_zid=buyer,
                amount=amount,
                description=description,
                invoice_id=invoice_id,
                synced=synced,
            )
            if synced:
                sello = (
                    "SELLADA en la Red"
                    " (verificable"
                    " offline)"
                )
            else:
                sello = (
                    "pendiente de sello"
                    " (Red no disponible,"
                    " quedara registrada)"
                )
            self._html(
                200,
                _page(
                    "Operacion registrada",
                    "<h1>Operacion #"
                    + str(row["seq"])
                    + "</h1>"
                    "<p>"
                    + kind
                    + ": $"
                    + str(amount)
                    + " - "
                    + sello
                    + "</p><p>Factura: <b>"
                    + (invoice_id
                       or "pendiente")
                    + "</b></p>"
                    "<a href='/nexo/contador'>"
                    "<button>Verificar como"
                    " contador</button></a>"
                    "<a href='/nexo'>"
                    "<button class='gray'>"
                    "Inicio</button></a>",
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
                        "app": "nexo",
                        "status":
                        "operational",
                    },
                },
            )
            return
        if s == ["ledger"]:
            self._send(
                200,
                {
                    "ok": True,
                    "data": list(
                        store
                        .list_operations()
                    ),
                },
            )
            return
        if s == ["ledger", "verify"]:
            self._send(
                200,
                {
                    "ok": True,
                    "data": {
                        "chain_intact": (
                            store
                            .verify_chain()
                        ),
                    },
                },
            )
            return
        if s == ["summary"]:
            self._send(
                200,
                {
                    "ok": True,
                    "data": store.summary(),
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
        if s == ["companies"]:
            company_id = (
                "EMP-"
                + uuid.uuid4().hex[:12]
            )
            row = store.add_company(
                company_id=company_id,
                zid=doc.get("zid"),
                name=self._req(doc, "name"),
                synced=False,
            )
            self._send(
                201,
                {
                    "ok": True,
                    "data": row,
                },
            )
            return
        if s == ["operations"]:
            row = store.record_operation(
                operation_id=(
                    "OP-"
                    + uuid.uuid4().hex[:12]
                ),
                kind=self._req(
                    doc, "kind"
                ),
                seller_zid=self._req(
                    doc, "seller_zid"
                ),
                buyer_zid=self._req(
                    doc, "buyer_zid"
                ),
                amount=float(
                    doc.get("amount", 0)
                ),
                description=self._req(
                    doc, "description"
                ),
                invoice_id=None,
                synced=False,
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
            "<h1>💠 NEXO</h1>"
            "<p>El nucleo contable"
            " sobre la Red: cada"
            " operacion queda"
            " encadenada y firmada -"
            " el contador solo"
            " verifica.</p>"
            "<h2>Registrar empresa"
            "</h2>"
            "<div class='card'>"
            "<form method='POST'"
            " action='/nexo/register'>"
            "<input name='name'"
            " placeholder='Nombre de la"
            " empresa'>"
            "<button>Registrar en la"
            " Red</button>"
            "</form></div>"
            "<h2>Registrar operacion"
            "</h2>"
            "<div class='card'>"
            "<form method='POST'"
            " action='/nexo/operation'>"
            "<input name='seller_zid'"
            " placeholder='ZID del"
            " vendedor'>"
            "<input name='buyer_zid'"
            " placeholder='ZID del"
            " comprador'>"
            "<select name='kind'>"
            "<option value='venta'>"
            "Venta</option>"
            "<option value='compra'>"
            "Compra</option>"
            "<option value='pago'>"
            "Pago</option>"
            "<option value='cobro'>"
            "Cobro</option>"
            "<option value='ajuste'>"
            "Ajuste</option>"
            "</select>"
            "<input name='amount'"
            " placeholder='Monto'>"
            "<input name='description'"
            " placeholder='Descripcion'>"
            "<button>Registrar y sellar"
            " factura</button>"
            "</form></div>"
            "<a href='/nexo/contador'>"
            "<button class='gray'>Soy"
            " contador (verificar)"
            "</button></a>"
            "<a href='/nexo/ledger'>"
            "<button class='gray'>Ver"
            " libro</button></a>"
        )
        self._html(200, _page("NEXO", body))

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


class NexoServer(ThreadingHTTPServer):
    daemon_threads = True
    allow_reuse_address = True

    def __init__(
        self, address: tuple[str, int]
    ) -> None:
        super().__init__(
            address, NexoApiHandler
        )

    @property
    def bound_port(self) -> int:
        return int(
            self.server_address[1]
        )


def serve_nexo(
    store: NexoStore,
    client: NetworkClient,
    *,
    host: str = "127.0.0.1",
    port: int = 0,
) -> NexoServer:
    NexoApiHandler.store = store
    NexoApiHandler.link = NexoLink(client)
    return NexoServer((host, port))
