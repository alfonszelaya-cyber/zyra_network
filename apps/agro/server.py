"""AGRO HTTP surface v3: role screens + JSON API
dual mode (N1 tests + N1b screens both work)."""
from __future__ import annotations

import json
import uuid
from http.server import (
    BaseHTTPRequestHandler,
    ThreadingHTTPServer,
)
from typing import Any, ClassVar
from urllib.parse import urlparse

from apps.agro.infrastructure.persistence.agro_store import (
    ROLES,
    AgroStore,
)
from apps.agro.infrastructure.network.network_client import (
    NetworkClient,
)
from apps.agro.modules.comercializacion.alertas_de_mercado.market_alert_service import (
    MarketAlertService,
)
from apps.agro.services.zyra_link import ZyraLink

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


class AgroApiHandler(
    BaseHTTPRequestHandler
):
    store: ClassVar[AgroStore]
    link: ClassVar[ZyraLink]
    client: ClassVar[NetworkClient]
    alerts: ClassVar[MarketAlertService] = (
        MarketAlertService()
    )

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
            self._send(
                404,
                {
                    "ok": False,
                    "error": {
                        "type":
                        "not_found",
                        "message": str(
                            exc
                        ),
                    },
                },
            )
        except ValueError as exc:
            self._send(
                400,
                {
                    "ok": False,
                    "error": {
                        "type":
                        "invalid_request",
                        "message": str(
                            exc
                        ),
                    },
                },
            )
        except Exception as exc:
            self._send(
                500,
                {
                    "ok": False,
                    "error": {
                        "type":
                        "internal_error",
                        "message": str(
                            exc
                        ),
                    },
                },
            )

    def _route(self, method: str) -> None:
        path = urlparse(self.path).path
        segments = [
            s
            for s in path.split("/")
            if s
        ]
        if segments[:1] != ["agro"]:
            self._send(
                404,
                {
                    "ok": False,
                    "error": {
                        "type":
                        "not_found",
                        "message":
                        "outside /agro",
                    },
                },
            )
            return
        tail = segments[1:]
        if method == "GET":
            self._get(tail)
        else:
            self._post(tail)

    def _get(self, s: list[str]) -> None:
        store = type(self).store
        if s == ["health"]:
            self._send(
                200,
                {
                    "ok": True,
                    "data": {
                        "app": "agro",
                        "status":
                        "operational",
                    },
                },
            )
            return
        if s == ["menu"]:
            self._send(
                200,
                {
                    "ok": True,
                    "data": {
                        "title": "AGRO",
                        "actions": [
                            {
                                "label":
                                "Vender mi"
                                " cosecha",
                                "route":
                                "/agro/production",
                            },
                            {
                                "label":
                                "Mi historial",
                                "route":
                                "/agro/government/summary",
                            },
                        ],
                    },
                },
            )
            return
        if s == ["producers"]:
            self._send(
                200,
                {
                    "ok": True,
                    "data": list(
                        store.list_producers()
                    ),
                },
            )
            return
        if s == ["government", "summary"]:
            self._send(
                200,
                {
                    "ok": True,
                    "data": store.summary(),
                },
            )
            return
        if not s or s == ["home"]:
            self._home()
            return
        if s[0] == "productor":
            self._screen_producer(s)
            return
        if s[0] == "gobierno":
            self._screen_government()
            return
        if s[0] == "banco":
            self._screen_bank()
            return
        self._send(
            404,
            {
                "ok": False,
                "error": {
                    "type": "not_found",
                    "message":
                    "unknown route",
                },
            },
        )

    def _post(self, s: list[str]) -> None:
        store = type(self).store
        link = type(self).link
        content_type = self.headers.get(
            "Content-Type", ""
        )
        is_json = (
            "application/json"
            in content_type
        )
        if s == ["producers"]:
            if is_json:
                doc = self._read_json()
            else:
                doc = self._read_form()
            name = self._req(doc, "name")
            producer_type = self._req(
                doc, "producer_type"
            )
            role = str(
                doc.get("role", "agricultor")
            )
            if role not in ROLES:
                raise ValueError(
                    f"unknown role: {role}"
                )
            location = doc.get("location")
            location = (
                str(location)
                if location is not None
                else None
            )
            producer_id = (
                "PRD-"
                + uuid.uuid4().hex[:12]
            )
            zid: str | None = None
            synced = False
            ok, data, _error = (
                link.register_producer_zid(
                    name
                )
            )
            if ok and data is not None:
                zid = str(data.get("zid"))
                synced = True
            row = store.add_producer(
                producer_id=producer_id,
                zid=zid,
                name=name,
                producer_type=(
                    producer_type
                ),
                role=role,
                location=location,
                synced=synced,
            )
            if is_json:
                self._send(
                    201,
                    {
                        "ok": True,
                        "data": row,
                    },
                )
            else:
                self._html(
                    200,
                    _page(
                        "Bienvenido a AGRO",
                        "<h1>Registro listo"
                        "</h1><p>Tu ID: <b>"
                        + producer_id
                        + "</b></p>"
                        "<a href='/agro/productor/"
                        + producer_id
                        + "'><button>Ir a mi"
                        " panel</button></a>",
                    ),
                )
            return
        if s == ["production"]:
            if is_json:
                doc = self._read_json()
            else:
                doc = self._read_form()
            producer_id = self._req(
                doc, "producer_id"
            )
            producer = store.get_producer(
                producer_id
            )
            product = self._req(
                doc, "product"
            )
            quantity = float(
                doc.get("quantity", 0)
            )
            if quantity <= 0:
                raise ValueError(
                    "quantity must be"
                    " positive"
                )
            unit = self._req(doc, "unit")
            network_seq: int | None = None
            zid = producer.get("zid")
            if zid is not None:
                ok, data, _error = (
                    link.record_agro_event(
                        str(zid),
                        "production",
                        f"{product}:"
                        f" {quantity}"
                        f" {unit}",
                    )
                )
                if (
                    ok
                    and data is not None
                ):
                    network_seq = int(
                        data.get("seq", 0)
                    )
            row = store.add_production(
                production_id=(
                    "PRO-"
                    + uuid.uuid4().hex[:12]
                ),
                producer_id=producer_id,
                product=product,
                quantity=quantity,
                unit=unit,
                network_seq=network_seq,
            )
            if is_json:
                self._send(
                    201,
                    {
                        "ok": True,
                        "data": row,
                    },
                )
            else:
                self._html(
                    200,
                    _page(
                        "Cosecha"
                        " registrada",
                        "<h1>Guardado en la"
                        " Red</h1><a href="
                        "'/agro'><button>"
                        "Inicio</button></a>",
                    ),
                )
            return
        if s == ["alerts", "evaluate"]:
            doc = self._read_json()
            previous = float(
                doc.get("previous_price", 0)
            )
            current = float(
                doc.get("current_price", 0)
            )
            result = (
                type(self).alerts.evaluate(
                    previous, current
                )
            )
            self._send(
                200,
                {
                    "ok": True,
                    "data": result,
                },
            )
            return
        if s == ["register"]:
            doc = self._read_form()
            name = self._req(doc, "name")
            producer_type = self._req(
                doc, "producer_type"
            )
            role = str(
                doc.get("role", "agricultor")
            )
            if role not in ROLES:
                raise ValueError(
                    f"unknown role: {role}"
                )
            location = doc.get("location")
            location = (
                str(location)
                if location is not None
                else None
            )
            producer_id = (
                "PRD-"
                + uuid.uuid4().hex[:12]
            )
            zid: str | None = None
            ok, data, _error = (
                link.register_producer_zid(
                    name
                )
            )
            if ok and data is not None:
                zid = str(data.get("zid"))
            store.add_producer(
                producer_id=producer_id,
                zid=zid,
                name=name,
                producer_type=(
                    producer_type
                ),
                role=role,
                location=location,
                synced=(
                    zid is not None
                ),
            )
            self._html(
                200,
                _page(
                    "Bienvenido a AGRO",
                    "<h1>Registro listo"
                    "</h1><p>Tu ID: <b>"
                    + producer_id
                    + "</b></p>"
                    "<a href='/agro/productor/"
                    + producer_id
                    + "'><button>Ir a mi"
                    " panel</button></a>",
                ),
            )
            return
        if s == ["verify"]:
            doc = self._read_form()
            producer_id = self._req(
                doc, "producer_id"
            )
            row = store.get_producer(
                producer_id
            )
            zid = row.get("zid")
            if zid is None:
                raise ValueError(
                    "producer has no"
                    " network ZID yet"
                )
            ok, _data, _error = (
                link.complete_trust(
                    str(zid)
                )
            )
            if not ok:
                raise ValueError(
                    "network trust failed"
                )
            store.mark_verified(
                producer_id=producer_id
            )
            self._html(
                200,
                _page(
                    "Verificado",
                    "<h1>Productor"
                    " VERIFICADO</h1>"
                    "<a href='/agro/productor/"
                    + producer_id
                    + "'><button>Ir a mi"
                    " panel</button></a>",
                ),
            )
            return
        self._send(
            404,
            {
                "ok": False,
                "error": {
                    "type": "not_found",
                    "message":
                    "unknown route",
                },
            },
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

    def _home(self) -> None:
        body = (
            "<h1>🛡️ AGRO</h1>"
            "<p>La Red de confianza para"
            " agricultores y ganaderos."
            "</p>"
            "<h2>Soy productor</h2>"
            "<div class='card'>"
            "<form method='POST'"
            " action='/agro/register'>"
            "<input name='name'"
            " placeholder='Mi nombre'>"
            "<select name='role'>"
            "<option value='agricultor'>"
            "Agricultor</option>"
            "<option value='ganadero'>"
            "Ganadero</option>"
            "</select>"
            "<input name='producer_type'"
            " placeholder='Que produzco"
            " (maiz, ganado...)'>"
            "<input name='location'"
            " placeholder='Mi zona'>"
            "<button>Registrarme en la"
            " Red</button>"
            "</form></div>"
            "<h2>Soy Gobierno / Banco"
            "</h2>"
            "<div class='card'>"
            "<a href='/agro/gobierno'>"
            "<button>Vista Gobierno"
            "</button></a>"
            "<a href='/agro/banco'>"
            "<button class='gray'>Vista"
            " Banco</button></a>"
            "</div>"
        )
        self._html(200, _page("AGRO", body))

    def _screen_producer(
        self, s: list[str]
    ) -> None:
        store = type(self).store
        producer_id = (
            s[1] if len(s) > 1 else ""
        )
        row = store.get_producer(
            producer_id
        )
        zid = row.get("zid")
        verified = row.get("verified")
        if verified:
            badge = "✅ VERIFICADO"
            extra = ""
        else:
            badge = (
                "⚠️ Sin verificar"
                " (sin bonos)"
            )
            extra = (
                "<form method='POST'"
                " action='/agro/verify'>"
                "<input type='hidden'"
                " name='producer_id'"
                f" value='{producer_id}'>"
                "<button>Verificarme para"
                " recibir bonos</button>"
                "</form>"
            )
        mine = [
            p
            for p in (
                store.list_productions()
            )
            if p["producer_id"]
            == producer_id
        ]
        history = "".join(
            "<li>• "
            + p["product"]
            + ": "
            + str(p["quantity"])
            + " "
            + p["unit"]
            + "</li>"
            for p in mine
        )
        if not history:
            history = (
                "<li>Sin registros</li>"
            )
        body = (
            "<h1>Mi Panel — "
            + str(row.get("name"))
            + "</h1>"
            "<p>"
            + badge
            + " · Rol: "
            + str(row.get("role"))
            + "</p>"
            "<h2>Registrar mi cosecha"
            "</h2>"
            "<div class='card'>"
            "<form method='POST'"
            " action='/agro/production'>"
            "<input type='hidden'"
            " name='producer_id'"
            f" value='{producer_id}'>"
            "<input name='product'"
            " placeholder='Producto'>"
            "<input name='quantity'"
            " placeholder='Cantidad'>"
            "<select name='unit'>"
            "<option value='quintal'>"
            "quintal</option>"
            "<option value='libra'>"
            "libra</option>"
            "</select>"
            "<button>Guardar en la"
            " Red</button>"
            "</form></div>"
            "<h2>Mi historial</h2><ul>"
            + history
            + "</ul>"
            + extra
            + "<a href='/agro'><button"
            " class='gray'>Inicio"
            "</button></a>"
        )
        self._html(
            200,
            _page("AGRO - Mi panel", body),
        )

    def _screen_government(self) -> None:
        summary = type(
            self
        ).store.summary()
        total = summary["producers_total"]
        verified = summary[
            "producers_verified"
        ]
        by_role = summary[
            "producers_by_role"
        ]
        by_product = summary[
            "productions_by_product"
        ]
        roles_html = "".join(
            "<li>• "
            + k
            + ": "
            + str(v)
            + "</li>"
            for k, v in by_role.items()
        )
        if not roles_html:
            roles_html = (
                "<li>Sin datos</li>"
            )
        products_html = "".join(
            "<li>• "
            + k
            + ": "
            + str(v)
            + " quintales</li>"
            for k, v in (
                by_product.items()
            )
        )
        if not products_html:
            products_html = (
                "<li>Sin cosechas"
                " registradas</li>"
            )
        body = (
            "<h1>🏛️ AGRO — Vista"
            " Gobierno</h1>"
            "<h2>Soberania alimentaria"
            " nacional</h2>"
            "<div class='card'>"
            "<span class='big'>"
            + str(total)
            + "</span> productores<br>"
            "<span class='big'>"
            + str(verified)
            + "</span> verificados"
            "</div>"
            "<h2>Por rol</h2><ul>"
            + roles_html
            + "</ul>"
            "<h2>Produccion nacional"
            "</h2><ul>"
            + products_html
            + "</ul>"
            "<a href='/agro'><button"
            " class='gray'>Inicio"
            "</button></a>"
        )
        self._html(
            200,
            _page("AGRO - Gobierno", body),
        )

    def _screen_bank(self) -> None:
        producers = type(
            self
        ).store.list_producers()
        rows = ""
        for p in producers:
            if p["verified"]:
                estado = (
                    "✅ verificado"
                    " (elegible para"
                    " credito)"
                )
            else:
                estado = (
                    "⚠️ sin verificar"
                )
            rows = (
                rows
                + "<li>• "
                + str(p["name"])
                + " - "
                + str(p["role"])
                + " - "
                + estado
                + "</li>"
            )
        if not rows:
            rows = (
                "<li>Sin productores</li>"
            )
        body = (
            "<h1>🏦 AGRO — Vista Banco"
            "</h1>"
            "<p>Elegibilidad de credito:"
            " basada en verificacion de"
            " la Red.</p>"
            "<ul>"
            + rows
            + "</ul>"
            "<a href='/agro'><button"
            " class='gray'>Inicio"
            "</button></a>"
        )
        self._html(
            200,
            _page("AGRO - Banco", body),
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


class AgroServer(ThreadingHTTPServer):
    daemon_threads = True
    allow_reuse_address = True

    def __init__(
        self, address: tuple[str, int]
    ) -> None:
        super().__init__(
            address, AgroApiHandler
        )

    @property
    def bound_port(self) -> int:
        return int(
            self.server_address[1]
        )


def serve_agro(
    store: AgroStore,
    client: NetworkClient,
    *,
    host: str = "127.0.0.1",
    port: int = 0,
) -> AgroServer:
    AgroApiHandler.store = store
    AgroApiHandler.link = ZyraLink(client)
    AgroApiHandler.client = client
    return AgroServer((host, port))
