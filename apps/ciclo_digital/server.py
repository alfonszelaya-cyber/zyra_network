"""CICLO-DIGITAL HTTP surface."""
from __future__ import annotations

import json
import uuid
from http.server import (
    BaseHTTPRequestHandler,
    ThreadingHTTPServer,
)
from typing import Any, ClassVar
from urllib.parse import urlparse

from apps.ciclo_digital.infrastructure.persistence.ciclo_store import (
    CicloStore,
)
from apps.ciclo_digital.infrastructure.network.network_client import (
    NetworkClient,
)
from apps.ciclo_digital.services.ciclo_link import (
    CicloLink,
)
from apps.ciclo_digital.services.ciclo_link_ext import (
    CicloLinkExt,
)
import uuid as _uuid

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
    "input,textarea{width:100%;box-sizing:"
    "border-box;background:#0d1117;color:#e6edf3;"
    "border:1px solid #30363d;border-radius:6px;"
    "padding:8px;margin:4px 0;font-size:0.95rem}"
    ".big{font-size:1.6rem;font-weight:bold;"
    "color:#58a6ff}"
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


class CicloApiHandler(
    BaseHTTPRequestHandler
):
    store: ClassVar[CicloStore]
    link: ClassVar[CicloLink]
    client: ClassVar[NetworkClient]

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
        if segments[:1] != ["ciclo"]:
            self._html(
                404,
                _page(
                    "404",
                    "<h1>Fuera de"
                    " CICLO</h1>",
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
        if s[0] == "arqueologia" and len(s) == 2:
            self._screen_archaeology(s[1])
            return
        if s == ["global"]:
            self._send(
                200,
                {"ok": True, "data": self.store.global_recycling_stats()},
            )
            return
        if (
            s[0] == "balance"
            and len(s) == 2
        ):
            zid = s[1]
            items = store.list_recycled(
                owner_zid=zid
            )
            total_tokens = 0
            items_html = ""
            for it in items:
                total_tokens += it[
                    "token_amount"
                ]
                items_html = (
                    items_html
                    + "<li>• "
                    + it["description"]
                    + " ("
                    + str(
                        it["token_amount"]
                    )
                    + " tokens)</li>"
                )
            if not items_html:
                items_html = (
                    "<li>Sin reciclajes"
                    " aun</li>"
                )
            body = (
                "<h1>♻️ Mi Reciclaje"
                "</h1>"
                "<div class='card'>"
                "<span class='big'>"
                + str(total_tokens)
                + "</span> tokens ganados"
                "</div><ul>"
                + items_html
                + "</ul>"
                "<a href='/ciclo'>"
                "<button class='gray'>"
                "Inicio</button></a>"
            )
            self._html(
                200,
                _page(
                    "CICLO - Reciclaje",
                    body,
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
        if s == ["arch-case"]:
            self._arch_case_form(doc)
            return
        if s == ["arch-finding"]:
            self._arch_finding_form(doc)
            return
        if s == ["arch-reconstruct"]:
            self._arch_reconstruct_form(doc)
            return
        if s == ["arch-seal"]:
            self._arch_seal_form(doc)
            return
        if s == ["recycle"]:
            owner_zid = self._req(
                doc, "owner_zid"
            )
            description = self._req(
                doc, "description"
            )
            item_id = (
                "REC-"
                + uuid.uuid4().hex[:10]
            )
            sealed_doc: str | None = None
            ok, data, _error = (
                link.seal_recycled(
                    owner_zid=owner_zid,
                    item_id=item_id,
                    description=(
                        description
                    ),
                )
            )
            if ok and data is not None:
                sealed_doc = str(
                    data.get(
                        "document_id"
                    )
                )
            earned = 0
            ok2, data2, _error2 = (
                link.earn_tokens(
                    subject_zid=owner_zid,
                    activity="reciclaje",
                    ref_id=item_id,
                )
            )
            if ok2 and data2 is not None:
                earned = 5
            import hashlib

            data_hash = hashlib.sha256(
                description.encode(
                    "utf-8"
                )
            ).hexdigest()
            row = store.add_recycled(
                item_id=item_id,
                owner_zid=owner_zid,
                description=description,
                data_hash=data_hash,
                token_amount=earned,
                document_id=sealed_doc,
                synced=True,
            )
            self._html(
                200,
                _page(
                    "Reciclado",
                    "<h1>♻️ Dato"
                    " reciclado</h1>"
                    "<p>Ganaste <b>"
                    + str(earned)
                    + " tokens</b></p>"
                    "<p>Sellado en la Red:"
                    " "
                    + (
                        sealed_doc
                        or "pendiente"
                    )
                    + "</p><a href='/ciclo/"
                    "balance/"
                    + owner_zid
                    + "'><button>Ver mis"
                    " tokens</button></a>"
                    "<a href='/ciclo'>"
                    "<button class='gray'>"
                    "Inicio</button></a>",
                ),
            )
            return
        if s == ["recover"]:
            query = self._req(
                doc, "query"
            )
            result = link.search_network(
                app_id="ciclo",
                query=query,
            )
            if not result[0]:
                raise ValueError(
                    result[2]
                    or "busqueda fallo"
                )
            data = result[1] or {}
            items = data.get("items", [])
            html_items = ""
            for h in items:
                html_items = (
                    html_items
                    + "<li>• ["
                    + h.get("source", "")
                    + "] "
                    + h.get("title", "")
                    + "</li>"
                )
            if not html_items:
                html_items = (
                    "<li>Sin resultados"
                    " recuperables</li>"
                )
            self._html(
                200,
                _page(
                    "Arqueologia digital",
                    "<h1>🔍 Recuperado de"
                    " la Red</h1><ul>"
                    + html_items
                    + "</ul>"
                    "<a href='/ciclo'>"
                    "<button class='gray'>"
                    "Inicio</button></a>",
                ),
            )
            return
        if s == ["export-evidence"]:
            subject_zid = self._req(
                doc, "subject_zid"
            )
            purpose = self._req(
                doc, "purpose"
            )
            ok, data, _error = (
                link.export_evidence(
                    subject_zid=(
                        subject_zid
                    ),
                    entries=[
                        [
                            "evidence",
                            "EXP-1",
                            purpose,
                        ]
                    ],
                )
            )
            if not (
                ok and data is not None
            ):
                raise ValueError(
                    "export fallo"
                )
            bundle_id = str(
                data.get("bundle_id")
            )
            export_id = (
                "EXP-"
                + uuid.uuid4().hex[:10]
            )
            store.record_export(
                export_id=export_id,
                subject_zid=subject_zid,
                bundle_id=bundle_id,
                purpose=purpose,
            )
            self._html(
                200,
                _page(
                    "Evidencia exportada",
                    "<h1>📦 Evidencia"
                    " exportada</h1>"
                    "<p>Firmada y portable"
                    " para el juzgado.</p>"
                    "<p>Bundle: <b>"
                    + bundle_id
                    + "</b></p>"
                    "<a href='/ciclo'>"
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
                        "app":
                        "ciclo_digital",
                        "status":
                        "operational",
                    },
                },
            )
            return
        if s[:1] == ["recycled"] and len(
            s
        ) == 2:
            self._send(
                200,
                {
                    "ok": True,
                    "data": list(
                        store.list_recycled(
                            owner_zid=s[1]
                        )
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
        if s == ["recycling", "global"]:
            self._api_global_recycling(doc)
            return
        if s == ["archaeology", "cases"]:
            self._api_arch_case(doc)
            return
        if s == ["archaeology", "findings"]:
            self._api_arch_finding(doc)
            return
        if s == ["archaeology", "reconstruct"]:
            self._api_arch_reconstruct(doc)
            return
        if s == ["recycling", "value"]:
            self._api_value(doc)
            return
        doc = self._read_json()
        if s == ["recycled"]:
            item_id = (
                "REC-"
                + uuid.uuid4().hex[:10]
            )
            row = store.add_recycled(
                item_id=item_id,
                owner_zid=self._req(
                    doc, "owner_zid"
                ),
                description=self._req(
                    doc, "description"
                ),
                data_hash=self._req(
                    doc, "data_hash"
                ),
                token_amount=int(
                    doc.get(
                        "token_amount", 0
                    )
                ),
                document_id=None,
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

    def _ext(self) -> CicloLinkExt:
        link = type(self).link
        return CicloLinkExt(
            getattr(link, "_client")
        )

    def _api_global_recycling(self, doc) -> None:
        store = type(self).store
        ext = self._ext()
        source_app = self._req(doc, "source_app")
        owner_zid = self._req(doc, "owner_zid")
        description = self._req(doc, "description")
        category = self._req(doc, "category")
        condition = str(doc.get("condition", "bueno"))
        event = store.add_global_recycling(
            event_id="GLB-" + _uuid.uuid4().hex[:10],
            source_app=source_app,
            owner_zid=owner_zid,
            description=description,
            category=category,
            condition_state=condition,
            document_id=None,
        )
        tokens_ok = False
        try:
            ok, _data = ext.earn_tokens(
                subject_zid=owner_zid,
                activity="reciclaje",
                ref_id=event["event_id"],
            )
            tokens_ok = bool(ok)
        except Exception:
            tokens_ok = False
        self._send(
            201,
            {
                "ok": True,
                "data": {
                    "event_id": event["event_id"],
                    "source_app": event["source_app"],
                    "reward_tokens": event["reward_tokens"],
                    "network_tokens": tokens_ok,
                },
            },
        )

    def _api_arch_case(self, doc) -> None:
        store = type(self).store
        case = store.create_arch_case(
            case_id="ARC-" + _uuid.uuid4().hex[:10],
            owner_zid=self._req(doc, "owner_zid"),
            title=self._req(doc, "title"),
            description=self._req(doc, "description"),
        )
        self._send(201, {"ok": True, "data": case})

    def _api_arch_finding(self, doc) -> None:
        store = type(self).store
        finding = store.add_finding(
            finding_id="FND-" + _uuid.uuid4().hex[:10],
            case_id=self._req(doc, "case_id"),
            source=self._req(doc, "source"),
            title=self._req(doc, "title"),
            content=self._req(doc, "content"),
            certainty=self._req(doc, "certainty"),
            reason=doc.get("reason"),
            document_id=None,
        )
        self._send(201, {"ok": True, "data": finding})

    def _api_arch_reconstruct(self, doc) -> None:
        store = type(self).store
        reconstruction = store.add_reconstruction(
            reconstruction_id="RCN-" + _uuid.uuid4().hex[:10],
            case_id=self._req(doc, "case_id"),
            title=self._req(doc, "title"),
            description=self._req(doc, "description"),
            basis=self._req(doc, "basis"),
            certainty=self._req(doc, "certainty"),
        )
        self._send(201, {"ok": True, "data": reconstruction})

    def _api_value(self, doc) -> None:
        store = type(self).store
        item_id = self._req(doc, "item_id")
        category = self._req(doc, "category")
        condition = self._req(doc, "condition")
        valuation = store.add_valuation(
            valuation_id="VAL-" + _uuid.uuid4().hex[:10],
            item_id=item_id,
            category=category,
            condition=condition,
        )
        owner_zid = doc.get("owner_zid")
        if owner_zid is not None:
            ext = self._ext()
            ok, _data = ext.earn_tokens(
                subject_zid=str(owner_zid),
                activity="reciclaje",
                ref_id=item_id,
            )
            valuation["network_tokens"] = bool(ok)
        self._send(201, {"ok": True, "data": valuation})

    def _arch_case_form(self, doc) -> None:
        store = type(self).store
        owner_zid = self._req(doc, "owner_zid")
        title = self._req(doc, "title")
        description = self._req(doc, "description")
        case_id = "ARC-" + _uuid.uuid4().hex[:10]
        store.create_arch_case(
            case_id=case_id,
            owner_zid=owner_zid,
            title=title,
            description=description,
        )
        link_line = "<a href='/ciclo/arqueologia/" + case_id + "'><button>Abrir expediente</button></a>"
        self._html(
            200,
            _page(
                "Expediente creado",
                "<h1>Expediente arqueologico</h1>"
                "<p>" + case_id + "</p>"
                + link_line
            ),
        )

    def _arch_finding_form(self, doc) -> None:
        store = type(self).store
        ext = self._ext()
        case_id = self._req(doc, "case_id")
        source = self._req(doc, "source")
        title = self._req(doc, "title")
        content = self._req(doc, "content")
        certainty = self._req(doc, "certainty")
        case = store.get_arch_case(case_id)
        document_id = None
        if case["owner_zid"]:
            ok, doc_id = ext.seal_document(
                owner_zid=case["owner_zid"],
                title="Hallazgo " + title,
                content=content,
            )
            if ok and doc_id:
                document_id = doc_id
        finding = store.add_finding(
            finding_id="FND-" + _uuid.uuid4().hex[:10],
            case_id=case_id,
            source=source,
            title=title,
            content=content,
            certainty=certainty,
            reason=None,
            document_id=document_id,
        )
        back_line = "<a href='/ciclo/arqueologia/" + case_id + "'><button>Volver al expediente</button></a>"
        self._html(
            200,
            _page(
                "Hallazgo registrado",
                "<h1>Hallazgo registrado</h1>"
                "<p>Certeza: " + certainty + "</p>"
                "<p>Hash: " + finding["content_hash"] + "</p>"
                + back_line
            ),
        )

    def _arch_reconstruct_form(self, doc) -> None:
        store = type(self).store
        case_id = self._req(doc, "case_id")
        title = self._req(doc, "title")
        description = self._req(doc, "description")
        basis = self._req(doc, "basis")
        certainty = self._req(doc, "certainty")
        store.add_reconstruction(
            reconstruction_id="RCN-" + _uuid.uuid4().hex[:10],
            case_id=case_id,
            title=title,
            description=description,
            basis=basis,
            certainty=certainty,
        )
        back_line = "<a href='/ciclo/arqueologia/" + case_id + "'><button>Volver al expediente</button></a>"
        self._html(
            200,
            _page(
                "Reconstruccion registrada",
                "<h1>Reconstruccion registrada</h1>"
                "<p>Certeza: " + certainty + "</p>"
                + back_line
            ),
        )

    def _arch_seal_form(self, doc) -> None:
        store = type(self).store
        ext = self._ext()
        case_id = self._req(doc, "case_id")
        case = store.get_arch_case(case_id)
        findings = store.list_findings(case_id=case_id)
        content = (
            "EXPEDIENTE " + case_id
            + " | " + case["title"]
            + " | hallazgos: " + str(len(findings))
        )
        sealed_doc = None
        if case["owner_zid"]:
            ok, doc_id = ext.seal_document(
                owner_zid=case["owner_zid"],
                title="Expediente " + case_id,
                content=content,
            )
            if ok and doc_id:
                sealed_doc = doc_id
        case = store.seal_arch_case(
            case_id=case_id,
            sealed_doc=sealed_doc or "local-pending",
        )
        self._html(
            200,
            _page(
                "Expediente sellado",
                "<h1>Expediente sellado</h1>"
                "<p>Documento: " + str(sealed_doc or "pendiente") + "</p>"
                "<a href='/ciclo'><button>Inicio</button></a>"
            ),
        )

    def _screen_archaeology(self, case_id: str) -> None:
        store = type(self).store
        case = store.get_arch_case(case_id)
        findings_html = ""
        for f in case["findings"]:
            findings_html = (
                findings_html
                + "<li>- " + f["title"]
                + " [" + f["certainty"] + "]</li>"
            )
        if not findings_html:
            findings_html = "<li>Sin hallazgos aun</li>"
        recon_html = ""
        for r in case["reconstructions"]:
            recon_html = (
                recon_html
                + "<li>- " + r["title"]
                + " [" + r["certainty"] + "]</li>"
            )
        if not recon_html:
            recon_html = "<li>Sin reconstrucciones aun</li>"
        back_line = "<a href='/ciclo'><button class='gray'>Inicio</button></a>"
        body = (
            "<h1>Expediente " + case_id + "</h1>"
            "<p>" + case["title"] + " | " + case["status"] + "</p>"
            "<h2>Hallazgos (certeza)</h2><ul>"
            + findings_html + "</ul>"
            "<h2>Reconstrucciones</h2><ul>"
            + recon_html + "</ul>"
            + back_line
        )
        self._html(200, _page("CICLO - Expediente", body))

    def _home(self) -> None:
        body = (
            "<h1>♻️ CICLO-DIGITAL</h1>"
            "<p>Nada muere: lo que se"
            " borra se recicla a"
            " tokens. Lo que se perdio"
            " se recupera con"
            " evidencia firmada.</p>"
            "<h2>♻️ Reciclar (borraste"
            " algo? ganate tokens)"
            "</h2>"
            "<div class='card'>"
            "<form method='POST'"
            " action='/ciclo/recycle'>"
            "<input name='owner_zid'"
            " placeholder='Tu ZID'>"
            "<input name='description'"
            " placeholder='Que dato"
            " borraste?'>"
            "<button>Reciclar y ganar"
            " tokens</button>"
            "</form></div>"
            "<h2>🔍 Arqueologia"
            " (recuperar evidencia"
            " perdida)</h2>"
            "<div class='card'>"
            "<form method='POST'"
            " action='/ciclo/recover'>"
            "<input name='query'"
            " placeholder='Que buscas"
            " recuperar?'>"
            "<button>Buscar en la"
            " Red</button>"
            "</form></div>"
            "<h2>📦 Exportar evidencia"
            " para juzgado</h2>"
            "<div class='card'>"
            "<form method='POST'"
            " action='/ciclo/"
            "export-evidence'>"
            "<input name='subject_zid'"
            " placeholder='ZID del"
            " titular'>"
            "<input name='purpose'"
            " placeholder='Proposito"
            " (caso, juzgado...)'>"
            "<button>Exportar firmado"
            "</button>"
            "</form></div>"
        )
        self._html(
            200, _page("CICLO", body)
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


class CicloServer(ThreadingHTTPServer):
    daemon_threads = True
    allow_reuse_address = True

    def __init__(
        self, address: tuple[str, int]
    ) -> None:
        super().__init__(
            address, CicloApiHandler
        )

    @property
    def bound_port(self) -> int:
        return int(
            self.server_address[1]
        )


def serve_ciclo(
    store: CicloStore,
    client: NetworkClient,
    *,
    host: str = "127.0.0.1",
    port: int = 0,
) -> CicloServer:
    CicloApiHandler.store = store
    CicloApiHandler.link = CicloLink(client)
    return CicloServer((host, port))
