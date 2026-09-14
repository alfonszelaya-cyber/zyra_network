"""AXIS clearance ops - standalone HTTP surface."""
from __future__ import annotations

import json

from http.server import (
    BaseHTTPRequestHandler,
    ThreadingHTTPServer,
)
from typing import ClassVar
from urllib.parse import urlparse

from apps.axis.life_history.access_control import (
    authorize,
)

_CSS = (
    "body{font-family:system-ui;"
    "background:#0d1117;color:#e6edf3;"
    "padding:20px;margin:0}"
    ".card{background:#161b22;border:1px"
    " solid #30363d;border-radius:10px;"
    "padding:14px;margin-top:10px}"
    "input{width:100%;box-sizing:border-box;"
    "background:#0d1117;color:#e6edf3;"
    "border:1px solid #30363d;"
    "border-radius:6px;padding:8px;"
    "margin:4px 0}"
    "button{background:#238636;color:#fff;"
    "border:none;padding:12px;"
    "border-radius:8px;width:100%;"
    "margin-top:6px}"
    ".ok{color:#3fb950}"
    ".bad{color:#f85149}"
)


def _page(title, body):
    return (
        "<!DOCTYPE html><html><head>"
        "<meta charset='utf-8'>"
        "<title>"
        + title
        + "</title><style>"
        + _CSS
        + "</style></head><body>"
        + body
        + "</body></html>"
    )


class ClearanceHandler(BaseHTTPRequestHandler):
    emitter: ClassVar[object] = None

    def log_message(self, fmt, *args):
        return None

    def do_GET(self):
        path = urlparse(self.path).path
        if path == "/clr/emision":
            self._show_form()
            return
        self._send_html(
            404,
            _page(
                "404",
                "<h1>No encontrado</h1>",
            ),
        )

    def do_POST(self):
        path = urlparse(self.path).path
        doc = self._read_form()
        if path == "/clr/emision":
            self._handle_emit(doc)
            return
        self._send_html(
            404,
            _page(
                "404",
                "<h1>No encontrado</h1>",
            ),
        )

    def _show_form(self):
        body = (
            "<h1>CERTIFICACION DE"
            " ANTECEDENTES</h1>"
            "<div class='card'>"
            "<form method='POST'"
            " action='/clr/emision'>"
            "<input name='operator_account'"
            " placeholder='Mi ID operador'>"
            "<input name='operator_role'"
            " placeholder='Mi rol (gobierno)'>"
            "<input name='subject_zid'"
            " placeholder='ZID del solicitante'>"
            "<button>Emitir certificacion"
            "</button>"
            "</form></div>"
        )
        self._send_html(
            200,
            _page(
                "AXIS - Certificaciones",
                body,
            ),
        )

    def _handle_emit(self, doc):
        emitter = type(self).emitter
        role = str(
            doc.get("operator_role", "")
        ).strip()
        try:
            if not authorize(
                "clearance.emit", role
            ):
                raise ValueError(
                    "rol no autorizado: "
                    + role
                )
            cert = emitter.emit(
                operator_account=self._field(
                    doc, "operator_account"
                ),
                operator_role=role,
                subject_zid=self._field(
                    doc, "subject_zid"
                ),
            )
            finding = cert["finding"]
            css = (
                "ok"
                if "SIN" in finding
                else "bad"
            )
            cert_json = json.dumps(
                {
                    "cert_id": cert["cert_id"],
                    "requester": cert[
                        "requester"
                    ],
                    "subject_zid": cert[
                        "subject_zid"
                    ],
                    "finding": finding,
                    "issued_at": cert[
                        "issued_at"
                    ],
                    "signature": cert[
                        "signature"
                    ],
                }
            )
            body = (
                "<h1>Certificacion emitida</h1>"
                "<p>ID: <b>"
                + cert["cert_id"]
                + "</b></p>"
                "<p>Resultado: <b class='"
                + css
                + "'>"
                + finding
                + "</b></p>"
                "<p>Documento: <b>"
                + str(
                    cert["document_id"] or "-"
                )
                + "</b></p>"
                "<p class='" + css + "'>"
                + cert_json
                + "</p>"
                "<a href='/clr/emision'>Volver</a>"
            )
            self._send_html(
                200,
                _page(
                    "AXIS - Certificacion",
                    body,
                ),
            )
        except Exception as exc:
            self._send_html(
                403,
                _page(
                    "Rechazado",
                    "<h1 class='bad'>Rechazada"
                    "</h1><p>"
                    + str(exc)
                    + "</p>"
                    "<a href='/clr/emision'>Volver</a>",
                ),
            )

    def _read_form(self):
        length = self.headers.get(
            "Content-Length"
        )
        raw = self.rfile.read(
            int(length)
        ).decode("utf-8")
        doc: dict = {}
        for pair in raw.split("&"):
            if "=" in pair:
                k, v = pair.split("=", 1)
                doc[k] = v.replace("+", " ")
        return doc

    @staticmethod
    def _field(doc, key):
        value = doc.get(key)
        if (
            not isinstance(value, str)
            or not value.strip()
        ):
            raise ValueError("missing: " + key)
        return value

    def _send_html(self, status, html):
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


class ClearanceServer(ThreadingHTTPServer):
    daemon_threads = True
    allow_reuse_address = True

    def __init__(self, address):
        super().__init__(
            address, ClearanceHandler
        )

    @property
    def bound_port(self):
        return int(self.server_address[1])


def serve_clearance(
    emitter,
    *,
    host="127.0.0.1",
    port=0,
):
    ClearanceHandler.emitter = emitter
    return ClearanceServer((host, port))
