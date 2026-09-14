"""AXIS ops server: justice & security screens.

Standalone additive HTTP surface on its own port.
Zero modification of existing server.py.

Routes:
  GET  /ops/justicia   case form
  POST /ops/justicia   open case (chained to life)
  GET  /ops/seguridad  incident form
  POST /ops/seguridad  report incident (chained)
"""
from __future__ import annotations

import json
import uuid
from http.server import (
    BaseHTTPRequestHandler,
    ThreadingHTTPServer,
)
from typing import ClassVar
from urllib.parse import urlparse

from apps.axis.life_history.justice_service import (
    JusticeLifeService,
)
from apps.axis.life_history.security_service import (
    SecurityLifeService,
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
)


def _page(title: str, body: str) -> str:
    return (
        "<!DOCTYPE html><html><head>"
        "<meta charset='utf-8'>"
        f"<title>{title}</title>"
        f"<style>{_CSS}</style></head>"
        f"<body>{body}</body></html>"
    )


class OpsHandler(BaseHTTPRequestHandler):
    store: ClassVar[object] = None
    life: ClassVar[object] = None

    def log_message(
        self, fmt, *args,
    ) -> None:
        return None

    def do_GET(self) -> None:
        path = urlparse(
            self.path
        ).path
        if path == "/ops/justicia":
            self._form_justicia()
            return
        if path == "/ops/seguridad":
            self._form_seguridad()
            return
        self._html(
            404,
            _page(
                "404",
                "<h1>No encontrado</h1>",
            ),
        )

    def do_POST(self) -> None:
        path = urlparse(
            self.path
        ).path
        doc = self._form()
        if path == "/ops/justicia":
            self._case(doc)
            return
        if path == "/ops/seguridad":
            self._incident(doc)
            return
        self._html(
            404,
            _page(
                "404",
                "<h1>No encontrado</h1>",
            ),
        )

    def _form_justicia(self) -> None:
        body = (
            "<h1>JUSTICIA</h1>"
            "<div class='card'>"
            "<form method='POST'"
            " action='/ops/justicia'>"
            "<input name='client_account'"
            " placeholder='ID cliente'>"
            "<input name='lawyer_account'"
            " placeholder='Mi ID abogado'>"
            "<input name='detail'"
            " placeholder='Detalle'>"
            "<button>Registrar caso"
            "</button>"
            "</form></div>"
            "<a href='/ops/seguridad'>"
            "Seguridad</a>"
        )
        self._html(
            200,
            _page(
                "AXIS - Justicia",
                body,
            ),
        )

    def _form_seguridad(self) -> None:
        body = (
            "<h1>SEGURIDAD</h1>"
            "<div class='card'>"
            "<form method='POST'"
            " action='/ops/seguridad'>"
            "<input name='police_account'"
            " placeholder='Mi ID policia'>"
            "<input name='subject_account'"
            " placeholder='ID sujeto'>"
            "<input name='description'"
            " placeholder='Descripcion'>"
            "<button>Reportar incidente"
            "</button>"
            "</form></div>"
            "<a href='/ops/justicia'>"
            "Justicia</a>"
        )
        self._html(
            200,
            _page(
                "AXIS - Seguridad",
                body,
            ),
        )

    def _case(self, doc) -> None:
        justice = JusticeLifeService(
            store=type(self).store,
            life=type(self).life,
        )
        case_id = (
            "CASE-"
            + uuid.uuid4().hex[:10]
        )
        opened = justice.open_case(
            case_id=case_id,
            client_account=self._req(
                doc, "client_account"
            ),
            lawyer_account=self._req(
                doc, "lawyer_account"
            ),
            detail=self._req(
                doc, "detail"
            ),
            stage="denuncia",
        )
        chained = (
            "SI"
            if opened["life_chained"]
            else "NO"
        )
        body = (
            "<h1>Caso "
            + case_id
            + "</h1><p>Encadenado: "
            + chained
            + "</p><a href='/ops/justicia'>"
            "Volver</a>"
        )
        self._html(
            200,
            _page("AXIS - Caso", body),
        )

    def _incident(self, doc) -> None:
        security = SecurityLifeService(
            store=type(self).store,
            life=type(self).life,
        )
        incident_id = (
            "INC-"
            + uuid.uuid4().hex[:10]
        )
        subject = doc.get(
            "subject_account"
        )
        subject = (
            str(subject).strip()
            if subject
            and str(subject).strip()
            else None
        )
        reported = (
            security.report_incident(
                incident_id=incident_id,
                police_account=(
                    self._req(
                        doc,
                        "police_account",
                    )
                ),
                description=self._req(
                    doc,
                    "description",
                ),
                subject_account=subject,
            )
        )
        chained = (
            "SI"
            if reported["life_chained"]
            else "NO"
        )
        body = (
            "<h1>Incidente "
            + incident_id
            + "</h1><p>Encadenado: "
            + chained
            + "</p><a href='/ops/seguridad'>"
            "Volver</a>"
        )
        self._html(
            200,
            _page(
                "AXIS - Incidente",
                body,
            ),
        )

    def _form(self) -> dict:
        length = self.headers.get(
            "Content-Length"
        )
        raw = self.rfile.read(
            int(length)
        ).decode("utf-8")
        doc: dict = {}
        for pair in raw.split("&"):
            if "=" in pair:
                k, v = pair.split(
                    "=", 1
                )
                doc[k] = v.replace(
                    "+", " "
                )
        return doc

    @staticmethod
    def _req(
        doc: dict, key: str,
    ) -> str:
        value = doc.get(key)
        if (
            not isinstance(value, str)
            or not value.strip()
        ):
            raise ValueError(
                "missing: " + key
            )
        return value

    def _html(
        self,
        status: int,
        html: str,
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


class OpsServer(ThreadingHTTPServer):
    daemon_threads = True
    allow_reuse_address = True

    def __init__(
        self, address,
    ) -> None:
        super().__init__(
            address, OpsHandler
        )

    @property
    def bound_port(self) -> int:
        return int(
            self.server_address[1]
        )


def serve_ops(
    store,
    life,
    *,
    host: str = "127.0.0.1",
    port: int = 0,
) -> OpsServer:
    OpsHandler.store = store
    OpsHandler.life = life
    return OpsServer((host, port))
