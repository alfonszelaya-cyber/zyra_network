"""MPE HTTP surface: role-based screens."""
from __future__ import annotations

import json
import uuid
from http.server import (
    BaseHTTPRequestHandler,
    ThreadingHTTPServer,
)
from typing import Any, ClassVar
from urllib.parse import urlparse

from apps.mi_primer_empleo.infrastructure.persistence.mpe_store import (
    MpeStore,
)
from apps.mi_primer_empleo.infrastructure.network.network_client import (
    NetworkClient,
)
from apps.mi_primer_empleo.services.mpe_link import (
    MpeLink,
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
    "font-size:1rem;cursor:pointer;margin:6px 4px 0 0;"
    "width:100%;text-align:left}"
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


class MpeApiHandler(
    BaseHTTPRequestHandler
):
    store: ClassVar[MpeStore]
    link: ClassVar[MpeLink]

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
        if segments[:1] != ["mpe"]:
            self._html(
                404,
                _page(
                    "404",
                    "<h1>Fuera de MPE"
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
        if s[0] == "trabajador":
            self._screen_worker(s)
            return
        if s[0] == "empresa":
            self._screen_company(s)
            return
        if s == ["jobs"]:
            jobs = store.list_jobs()
            items = "".join(
                "<li>• "
                + j["title"]
                + " ("
                + j["profession"]
                + ") - "
                + str(j["openings"])
                + " vacantes</li>"
                for j in jobs
            )
            if not items:
                items = (
                    "<li>Sin vacantes"
                    " abiertas</li>"
                )
            self._html(
                200,
                _page(
                    "MPE - Vacantes",
                    "<h1>Vacantes abiertas"
                    "</h1><ul>"
                    + items
                    + "</ul>"
                    "<a href='/mpe'>"
                    "<button class='gray'>"
                    "Inicio</button></a>",
                ),
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
            role = str(
                doc.get("role", "trabajador")
            )
            profession = doc.get(
                "profession"
            )
            profession = (
                str(profession)
                if profession is not None
                else None
            )
            account_id = (
                "MPE-"
                + uuid.uuid4().hex[:12]
            )
            zid: str | None = None
            if role == "trabajador":
                ok, data, _error = (
                    link.register_user(name)
                )
            else:
                ok, data, _error = (
                    link.register_company(
                        name
                    )
                )
            if ok and data is not None:
                zid = str(data.get("zid"))
            store.add_account(
                account_id=account_id,
                zid=zid,
                name=name,
                role=role,
                profession=profession,
            )
            zid_text = (
                zid
                if zid is not None
                else "pendiente de conexion"
            )
            self._html(
                200,
                _page(
                    "Bienvenido a MPE",
                    "<h1>Cuenta creada"
                    "</h1>"
                    "<p>Tu ID:"
                    f" <b>{account_id}"
                    "</b></p>"
                    "<p>Tu ZID de red: "
                    f"<b>{zid_text}</b></p>"
                    "<a href='/mpe/"
                    f"{role}/{account_id}'>"
                    "<button>Ir a mi panel"
                    "</button></a>",
                ),
            )
            return
        if s == ["job"]:
            company_account = self._req(
                doc, "company_account"
            )
            row = store.post_job(
                job_id=(
                    "JOB-"
                    + uuid.uuid4().hex[:10]
                ),
                company_account=(
                    company_account
                ),
                title=self._req(
                    doc, "title"
                ),
                profession=self._req(
                    doc, "profession"
                ),
                openings=int(
                    doc.get("openings", 1)
                ),
            )
            self._html(
                200,
                _page(
                    "Vacante publicada",
                    "<h1>Vacante publicada"
                    "</h1>"
                    f"<p>{row['title']} -"
                    f" {row['openings']}"
                    " vacantes</p>"
                    "<a href='/mpe/empresa/"
                    f"{company_account}'>"
                    "<button>Volver</button>"
                    "</a>",
                ),
            )
            return
        if s == ["apply"]:
            worker_account = self._req(
                doc, "worker_account"
            )
            app_id = (
                "APP-"
                + uuid.uuid4().hex[:10]
            )
            store.apply(
                application_id=app_id,
                job_id=self._req(
                    doc, "job_id"
                ),
                worker_account=(
                    worker_account
                ),
            )
            self._html(
                200,
                _page(
                    "Aplicacion enviada",
                    "<h1>Aplicacion"
                    " enviada</h1>"
                    "<a href='/mpe/trabajador/"
                    f"{worker_account}'>"
                    "<button>Volver</button>"
                    "</a>",
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
                        "app": "mpe",
                        "status":
                        "operational",
                    },
                },
            )
            return
        if s == ["jobs"]:
            self._send(
                200,
                {
                    "ok": True,
                    "data": list(
                        store.list_jobs()
                    ),
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
        if s == ["accounts"]:
            account_id = (
                "MPE-"
                + uuid.uuid4().hex[:12]
            )
            row = store.add_account(
                account_id=account_id,
                zid=doc.get("zid"),
                name=self._req(doc, "name"),
                role=self._req(doc, "role"),
                profession=doc.get(
                    "profession"
                ),
            )
            self._send(
                201,
                {
                    "ok": True,
                    "data": row,
                },
            )
            return
        if s == ["jobs"]:
            row = store.post_job(
                job_id=(
                    "JOB-"
                    + uuid.uuid4().hex[:10]
                ),
                company_account=self._req(
                    doc,
                    "company_account",
                ),
                title=self._req(
                    doc, "title"
                ),
                profession=self._req(
                    doc, "profession"
                ),
                openings=int(
                    doc.get("openings", 1)
                ),
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
            "<h1>💼 Mi Primer Empleo"
            "</h1>"
            "<p>Tu historial laboral"
            " VERIFICADO por la Red.</p>"
            "<h2>Soy trabajador</h2>"
            "<div class='card'>"
            "<form method='POST'"
            " action='/mpe/register'>"
            "<input type='hidden'"
            " name='role' value="
            "'trabajador'>"
            "<input name='name'"
            " placeholder='Mi nombre'>"
            "<input name='profession'"
            " placeholder='Mi oficio'>"
            "<button>Crear mi perfil"
            "</button>"
            "</form></div>"
            "<h2>Soy empresa</h2>"
            "<div class='card'>"
            "<form method='POST'"
            " action='/mpe/register'>"
            "<input type='hidden'"
            " name='role' value="
            "'empresa'>"
            "<input name='name'"
            " placeholder='Nombre de la"
            " empresa'>"
            "<input name='profession'"
            " placeholder='Sector'>"
            "<button>Registrar empresa"
            "</button>"
            "</form></div>"
            "<a href='/mpe/jobs'>"
            "<button class='gray'>Ver"
            " vacantes</button></a>"
        )
        self._html(200, _page("MPE", body))

    def _screen_worker(
        self, s: list[str]
    ) -> None:
        store = type(self).store
        account_id = (
            s[1] if len(s) > 1 else ""
        )
        row = store.get_account(
            account_id
        )
        jobs = store.list_jobs(
            profession=row.get(
                "profession"
            )
        )
        jobs_html = ""
        for j in jobs:
            jobs_html = (
                jobs_html
                + "<li>• "
                + j["title"]
                + " ("
                + j["profession"]
                + ") <form method='POST'"
                + " action='/mpe/apply'>"
                + "<input type='hidden'"
                + " name='job_id'"
                + " value='"
                + j["job_id"]
                + "'>"
                + "<input type='hidden'"
                + " name='worker_account'"
                + " value='"
                + account_id
                + "'>"
                + "<button>Aplicar"
                + "</button></form></li>"
            )
        if not jobs_html:
            jobs_html = (
                "<li>Sin vacantes para"
                " tu oficio</li>"
            )
        body = (
            "<h1>Mi Panel — "
            + str(row.get("name"))
            + "</h1>"
            "<h2>Vacantes para ti</h2>"
            f"<ul>{jobs_html}</ul>"
            "<a href='/mpe'><button"
            " class='gray'>Inicio"
            "</button></a>"
        )
        self._html(
            200,
            _page("MPE - Mi panel", body),
        )

    def _screen_company(
        self, s: list[str]
    ) -> None:
        store = type(self).store
        account_id = (
            s[1] if len(s) > 1 else ""
        )
        row = store.get_account(
            account_id
        )
        body = (
            "<h1>Panel Empresa — "
            + str(row.get("name"))
            + "</h1>"
            "<h2>Publicar vacante</h2>"
            "<div class='card'>"
            "<form method='POST'"
            " action='/mpe/job'>"
            "<input type='hidden'"
            " name='company_account'"
            f" value='{account_id}'>"
            "<input name='title'"
            " placeholder='Cargo'>"
            "<input name='profession'"
            " placeholder='Oficio'>"
            "<input name='openings'"
            " value='1'>"
            "<button>Publicar</button>"
            "</form></div>"
            "<a href='/mpe/jobs'>"
            "<button class='gray'>Ver"
            " vacantes</button></a>"
            "<a href='/mpe'><button"
            " class='gray'>Inicio"
            "</button></a>"
        )
        self._html(
            200,
            _page(
                "MPE - Empresa", body
            ),
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


class MpeServer(ThreadingHTTPServer):
    daemon_threads = True
    allow_reuse_address = True

    def __init__(
        self, address: tuple[str, int]
    ) -> None:
        super().__init__(
            address, MpeApiHandler
        )

    @property
    def bound_port(self) -> int:
        return int(
            self.server_address[1]
        )


def serve_mpe(
    store: MpeStore,
    client: NetworkClient,
    *,
    host: str = "127.0.0.1",
    port: int = 0,
) -> MpeServer:
    MpeApiHandler.store = store
    MpeApiHandler.link = MpeLink(client)
    return MpeServer((host, port))
