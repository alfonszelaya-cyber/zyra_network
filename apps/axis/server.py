"""AXIS HTTP surface: role-based screens."""
from __future__ import annotations

import json
import uuid
from http.server import (
    BaseHTTPRequestHandler,
    ThreadingHTTPServer,
)
from typing import Any, ClassVar
from urllib.parse import urlparse

from apps.axis.infrastructure.persistence.axis_store import (
    AxisStore,
)
from apps.axis.infrastructure.network.network_client import (
    NetworkClient,
)
from apps.axis.services.axis_link import AxisLink
from apps.axis.services.axis_link_ext import AxisLinkExt
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


class AxisApiHandler(
    BaseHTTPRequestHandler
):
    store: ClassVar[AxisStore]
    link: ClassVar[AxisLink]

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
        if segments[:1] != ["axis"]:
            self._html(
                404,
                _page(
                    "404",
                    "<h1>Fuera de AXIS"
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
        if s[0] == "emergencias":
            self._screen_emergencias()
            return
        if s[0] == "paciente":
            self._screen_patient(s)
            return
        if s[0] == "medico":
            self._screen_doctor(s)
            return
        if s[0] == "abogado":
            self._screen_lawyer(s)
            return
        if s[0] == "policia":
            self._screen_police()
            return
        if s == ["gobierno"]:
            self._screen_government()
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
                doc.get("role", "paciente")
            )
            account_id = (
                "AX-"
                + uuid.uuid4().hex[:12]
            )
            zid: str | None = None
            ok, data, _error = (
                link.register_person(name)
            )
            if ok and data is not None:
                zid = str(data.get("zid"))
            store.add_account(
                account_id=account_id,
                zid=zid,
                name=name,
                role=role,
            )
            self._html(
                200,
                _page(
                    "Cuenta AXIS creada",
                    "<h1>Cuenta creada"
                    "</h1>"
                    "<p>Tu ID: <b>"
                    + account_id
                    + "</b></p>"
                    "<p>Tu ZID: <b>"
                    + (zid or "pendiente")
                    + "</b></p>"
                    "<a href='/axis/"
                    + role
                    + "/"
                    + account_id
                    + "'><button>Ir a mi"
                    " panel</button></a>",
                ),
            )
            return
        if s == ["medical"]:
            patient_account = self._req(
                doc, "patient_account"
            )
            doctor_account = self._req(
                doc, "doctor_account"
            )
            diagnosis = self._req(
                doc, "diagnosis"
            )
            appointment = doc.get(
                "next_appointment"
            )
            appointment = (
                str(appointment)
                if appointment is not None
                else None
            )
            patient = store.get_account(
                patient_account
            )
            zid = patient.get("zid")
            sealed_doc: str | None = None
            if zid is not None:
                ok, data, _error = (
                    link.seal_evidence(
                        owner_zid=str(
                            zid
                        ),
                        evidence_id=(
                            "MED-"
                            + uuid.uuid4()
                            .hex[:8]
                        ),
                        title=(
                            "Diagnostico:"
                            " "
                            + diagnosis
                        ),
                        content=(
                            diagnosis.encode(
                                "utf-8"
                            )
                        ),
                    )
                )
                if (
                    ok
                    and data is not None
                ):
                    sealed_doc = str(
                        data.get(
                            "document_id"
                        )
                    )
            row = store.add_medical_record(
                record_id=(
                    "MED-"
                    + uuid.uuid4().hex[:10]
                ),
                patient_account=(
                    patient_account
                ),
                doctor_account=(
                    doctor_account
                ),
                diagnosis=diagnosis,
                next_appointment=(
                    appointment
                ),
                sealed_doc=sealed_doc,
            )
            if zid is not None:
                link.record_file_event(
                    str(zid),
                    "medical_record",
                    diagnosis,
                )
            cita = (
                row["next_appointment"]
                or "sin cita programada"
            )
            self._html(
                200,
                _page(
                    "Registro medico",
                    "<h1>Registro sellado"
                    " en la Red</h1>"
                    "<p>Diagnostico: "
                    + diagnosis
                    + "</p><p>Proxima cita:"
                    " "
                    + cita
                    + " (automatica)"
                    "</p>"
                    "<a href='/axis/medico/"
                    + doctor_account
                    + "'><button>Volver"
                    "</button></a>",
                ),
            )
            return
        if s == ["case"]:
            client_account = self._req(
                doc, "client_account"
            )
            lawyer_account = self._req(
                doc, "lawyer_account"
            )
            status = self._req(
                doc, "status"
            )
            if status not in (
                "proceso",
                "libre",
                "preso",
                "cerrado",
            ):
                raise ValueError(
                    "estado invalido"
                )
            detail = self._req(
                doc, "detail"
            )
            case_id = (
                "CASE-"
                + uuid.uuid4().hex[:10]
            )
            row = store.add_legal_case(
                case_id=case_id,
                client_account=(
                    client_account
                ),
                lawyer_account=(
                    lawyer_account
                ),
                status=status,
                detail=detail,
                sealed_doc=None,
            )
            link.record_file_event(
                client_account,
                "legal_case",
                f"{case_id}: {status}",
            )
            self._html(
                200,
                _page(
                    "Caso registrado",
                    "<h1>Caso"
                    f" {case_id}</h1>"
                    "<p>Estado: "
                    + status
                    + "</p>"
                    "<a href='/axis/abogado/"
                    + lawyer_account
                    + "'><button>Mis casos"
                    "</button></a>",
                ),
            )
            return
        if s == ["case-update"]:
            case_id = self._req(
                doc, "case_id"
            )
            lawyer_account = self._req(
                doc, "lawyer_account"
            )
            status = self._req(
                doc, "status"
            )
            detail = self._req(
                doc, "detail"
            )
            row = store.update_case_status(
                case_id=case_id,
                status=status,
                detail=detail,
                sealed_doc=None,
            )
            link.record_file_event(
                row["client_account"],
                "legal_case_update",
                f"{case_id}: {status}",
            )
            self._html(
                200,
                _page(
                    "Caso actualizado",
                    "<h1>Caso"
                    f" {case_id}</h1>"
                    "<p>Nuevo estado: "
                    + status
                    + "</p>"
                    "<a href='/axis/abogado/"
                    + lawyer_account
                    + "'><button>Mis casos"
                    "</button></a>",
                ),
            )
            return
        if s == ["exam"]:
            self._exam_form(doc)
            return
        if s == ["exam-result"]:
            self._exam_result_form(doc)
            return
        if s == ["incident"]:
            police_account = self._req(
                doc, "police_account"
            )
            description = self._req(
                doc, "description"
            )
            incident_id = (
                "INC-"
                + uuid.uuid4().hex[:10]
            )
            sealed_doc: str | None = None
            ok, data, _error = (
                link.seal_evidence(
                    owner_zid=(
                        police_account
                    ),
                    evidence_id=(
                        incident_id
                    ),
                    title=(
                        "Incidente "
                        + incident_id
                    ),
                    content=(
                        description.encode(
                            "utf-8"
                        )
                    ),
                )
            )
            if ok and data is not None:
                sealed_doc = str(
                    data.get(
                        "document_id"
                    )
                )
            store.add_incident(
                incident_id=incident_id,
                police_account=(
                    police_account
                ),
                description=(
                    description
                ),
                sealed_doc=sealed_doc,
            )
            self._html(
                200,
                _page(
                    "Incidente sellado",
                    "<h1>Incidente sellado"
                    " como evidencia</h1>"
                    f"<p>ID: {incident_id}"
                    "</p><p>Documento:"
                    f" {sealed_doc or '-'}"
                    "</p>"
                    "<a href='/axis/policia'>"
                    "<button>Volver"
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
                        "app": "axis",
                        "status":
                        "operational",
                    },
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
        if s == ["emergencies"]:
            self._emergency_create(doc)
            return
        if s == ["emergencies", "resolve"]:
            self._emergency_resolve(doc)
            return
        if (
            len(s) == 3
            and s[0] == "emergencies"
            and s[2] == "dispatch"
        ):
            self._emergency_dispatch(doc, s[1])
            return
        doc = self._read_json()
        if s == ["accounts"]:
            account_id = (
                "AX-"
                + uuid.uuid4().hex[:12]
            )
            row = store.add_account(
                account_id=account_id,
                zid=doc.get("zid"),
                name=self._req(doc, "name"),
                role=self._req(doc, "role"),
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

    def _ext(self) -> AxisLinkExt:
        link = type(self).link
        return AxisLinkExt(
            getattr(link, "_client")
        )

    def _exam_patient(self, exam_id: str) -> str:
        store = type(self).store
        row = store._db.query_one(
            "SELECT patient_account FROM axis_exams"
            " WHERE exam_id = ?",
            (exam_id,),
        )
        if row is None:
            raise LookupError("unknown exam: " + exam_id)
        return str(row["patient_account"])

    def _exam_form(self, doc) -> None:
        store = type(self).store
        patient_account = self._req(doc, "patient_account")
        doctor_account = self._req(doc, "doctor_account")
        exam_type = self._req(doc, "exam_type")
        exam_id = "EXM-" + _uuid.uuid4().hex[:10]
        row = store.add_exam(
            exam_id=exam_id,
            patient_account=patient_account,
            doctor_account=doctor_account,
            exam_type=exam_type,
        )
        self._html(
            200,
            _page(
                "Examen ordenado",
                "<h1>Examen ordenado</h1>"
                "<p>" + str(row["exam_id"])
                + " (" + exam_type + ")</p>"
                "<a href='/axis/medico/"
                + doctor_account
                + "'><button>Volver</button></a>"
            ),
        )

    def _exam_result_form(self, doc) -> None:
        store = type(self).store
        ext = self._ext()
        exam_id = self._req(doc, "exam_id")
        doctor_account = self._req(doc, "doctor_account")
        summary = self._req(doc, "summary")
        severity = self._req(doc, "severity")
        requires = (
            str(doc.get("requires_followup", ""))
            in ("1", "true", "si", "on")
        )
        reason = doc.get("followup_reason")
        reason = (
            str(reason) if reason is not None else None
        )
        patient_account = self._exam_patient(exam_id)
        patient = store.get_account(patient_account)
        zid = patient.get("zid")
        sealed_doc = None
        if zid is not None:
            ok, doc_id = ext.seal_evidence_canonical(
                owner_zid=str(zid),
                title="Resultado " + exam_id,
                content=summary,
            )
            if ok and doc_id:
                sealed_doc = doc_id
                ext.append_history(
                    zid=str(zid),
                    event="resultado_examen",
                    detail=exam_id + ": " + severity,
                )
        result = store.add_exam_result(
            result_id="RES-" + _uuid.uuid4().hex[:10],
            exam_id=exam_id,
            summary=summary,
            severity=severity,
            requires_followup=requires,
            followup_reason=reason,
            sealed_doc=sealed_doc,
        )
        cita = "no requiere seguimiento"
        if requires:
            appointment = store.create_appointment(
                appointment_id="APT-" + _uuid.uuid4().hex[:10],
                patient_account=patient_account,
                doctor_account=doctor_account,
                result_id=result["result_id"],
                reason=reason or "seguimiento de resultado",
                scheduled_at=str(
                    doc.get("scheduled_at", "por programar")
                ),
            )
            cita = appointment["scheduled_at"]
        self._html(
            200,
            _page(
                "Resultado registrado",
                "<h1>Resultado (sellado en la Red)</h1>"
                "<p>Severidad: " + severity + "</p>"
                "<p>Requiere seguimiento: " + str(requires) + "</p>"
                "<p>Cita automatica: " + cita + "</p>"
                "<p>El paciente sera recordado.</p>"
                "<a href='/axis/medico/"
                + doctor_account
                + "'><button>Volver</button></a>"
            ),
        )

    def _emergency_create(self, doc) -> None:
        store = type(self).store
        emergency_type = self._req(doc, "emergency_type")
        severity = self._req(doc, "severity")
        description = self._req(doc, "description")
        subject_account = doc.get("subject_account")
        subject_account_str = None
        if subject_account is not None:
            try:
                account = store.get_account(str(subject_account))
                subject_account_str = str(account["account_id"])
            except LookupError:
                subject_account_str = None
        emergency = store.create_emergency(
            emergency_id="EMG-" + _uuid.uuid4().hex[:10],
            source_app=str(doc.get("source_app", "manual")),
            subject_account=subject_account_str,
            subject_zid=None,
            emergency_type=emergency_type,
            severity=severity,
            description=description,
        )
        self._send(201, {"ok": True, "data": emergency})

    def _emergency_dispatch(self, doc, emergency_id: str) -> None:
        store = type(self).store
        agency = self._req(doc, "agency")
        priority = str(doc.get("priority", "alta"))
        emergency = store.dispatch_emergency(
            emergency_id=emergency_id,
            agency=agency,
            priority=priority,
        )
        self._send(200, {"ok": True, "data": emergency})

    def _emergency_resolve(self, doc) -> None:
        store = type(self).store
        emergency = store.resolve_emergency(
            emergency_id=self._req(doc, "emergency_id"),
        )
        self._send(200, {"ok": True, "data": emergency})

    def _screen_emergencias(self) -> None:
        store = type(self).store
        open_emergencies = store.list_open_emergencies()
        items = ""
        for e in open_emergencies:
            agencies = ", ".join(
                str(d["agency"]) for d in e["dispatches"]
            )
            items = (
                items
                + "<li>- " + e["emergency_id"]
                + " | " + e["emergency_type"]
                + " | " + e["severity"]
                + " | " + e["status"]
                + " | recursos: " + (agencies or "sin despachar")
                + "</li>"
            )
        if not items:
            items = "<li>Sin emergencias abiertas</li>"
        body = (
            "<h1>Centro de Emergencias</h1>"
            "<h2>Abiertas</h2><ul>" + items + "</ul>"
            "<a href='/axis'><button class='gray'>Inicio</button></a>"
        )
        self._html(
            200,
            _page("AXIS - Emergencias", body),
        )

    def _home(self) -> None:
        body = (
            "<h1>🏥⚖️🛡️ AXIS</h1>"
            "<p>Salud, justicia y"
            " seguridad con evidencia"
            " inmutable en la Red.</p>"
            "<h2>Registrarme</h2>"
            "<div class='card'>"
            "<form method='POST'"
            " action='/axis/register'>"
            "<input name='name'"
            " placeholder='Mi nombre'>"
            "<select name='role'>"
            "<option value='paciente'>"
            "Paciente</option>"
            "<option value='medico'>"
            "Medico</option>"
            "<option value='abogado'>"
            "Abogado</option>"
            "<option value='policia'>"
            "Policia</option>"
            "<option value='gobierno'>"
            "Gobierno</option>"
            "</select>"
            "<button>Crear cuenta"
            "</button>"
            "</form></div>"
            "<h2>Paneles</h2>"
            "<div class='card'>"
            "<p>Ingresa con tu ID de"
            " cuenta (AX-...):</p>"
            "<a href='/axis/gobierno'>"
            "<button>Vista Gobierno"
            "</button></a>"
            "</div>"
        )
        self._html(200, _page("AXIS", body))

    def _screen_patient(
        self, s: list[str]
    ) -> None:
        store = type(self).store
        account_id = (
            s[1] if len(s) > 1 else ""
        )
        row = store.get_account(
            account_id
        )
        records = (
            store.medical_records_of(
                patient_account=(
                    account_id
                )
            )
        )
        items = ""
        for r in records:
            cita = (
                r["next_appointment"]
                or "-"
            )
            items = (
                items
                + "<li>• "
                + r["diagnosis"]
                + " — proxima cita: "
                + cita
                + "</li>"
            )
        if not items:
            items = (
                "<li>Sin registros"
                " medicos</li>"
            )
        body = (
            "<h1>🩺 Mi Salud — "
            + str(row.get("name"))
            + "</h1>"
            "<p>Expediente medico"
            " inmutable en la Red.</p>"
            "<h2>Mis registros</h2>"
            f"<ul>{items}</ul>"
            "<a href='/axis'><button"
            " class='gray'>Inicio"
            "</button></a>"
        )
        self._html(
            200,
            _page("AXIS - Paciente", body),
        )

    def _screen_doctor(
        self, s: list[str]
    ) -> None:
        store = type(self).store
        account_id = (
            s[1] if len(s) > 1 else ""
        )
        row = store.get_account(
            account_id
        )
        patients = store.list_by_role(
            role="paciente"
        )
        options = ""
        for p in patients:
            options = (
                options
                + "<option value='"
                + p["account_id"]
                + "'>"
                + p["name"]
                + "</option>"
            )
        body = (
            "<h1>👨‍⚕️ Consultorio — "
            + str(row.get("name"))
            + "</h1>"
            "<h2>Nuevo registro (se"
            " sella en la Red)</h2>"
            "<div class='card'>"
            "<form method='POST'"
            " action='/axis/medical'>"
            "<input type='hidden'"
            " name='doctor_account'"
            f" value='{account_id}'>"
            "<select name="
            "'patient_account'>"
            + options
            + "</select>"
            "<input name='diagnosis'"
            " placeholder='Diagnostico'>"
            "<input name="
            "'next_appointment'"
            " placeholder='Proxima cita"
            " (auto al paciente)'>"
            "<button>Registrar y sellar"
            "</button>"
            "</form></div>"
            "<a href='/axis'><button"
            " class='gray'>Inicio"
            "</button></a>"
        )
        self._html(
            200,
            _page("AXIS - Medico", body),
        )

    def _screen_lawyer(
        self, s: list[str]
    ) -> None:
        store = type(self).store
        account_id = (
            s[1] if len(s) > 1 else ""
        )
        row = store.get_account(
            account_id
        )
        cases = store.cases_for(
            lawyer_account=account_id
        )
        items = ""
        for c in cases:
            items = (
                items
                + "<li>• "
                + c["case_id"]
                + " — "
                + c["status"]
                + " — "
                + c["detail"]
                + "</li>"
            )
        if not items:
            items = (
                "<li>Sin casos</li>"
            )
        body = (
            "<h1>⚖️ Mis Casos — "
            + str(row.get("name"))
            + "</h1>"
            f"<ul>{items}</ul>"
            "<h2>Nuevo caso</h2>"
            "<div class='card'>"
            "<form method='POST'"
            " action='/axis/case'>"
            "<input type='hidden'"
            " name='lawyer_account'"
            f" value='{account_id}'>"
            "<input name='client_account'"
            " placeholder='ID del"
            " cliente (AX-...)'>"
            "<select name='status'>"
            "<option value='proceso'>"
            "En proceso</option>"
            "<option value='libre'>"
            "Libre</option>"
            "<option value='preso'>"
            "Preso</option>"
            "<option value='cerrado'>"
            "Cerrado</option>"
            "</select>"
            "<input name='detail'"
            " placeholder='Detalle'>"
            "<button>Registrar caso"
            "</button>"
            "</form></div>"
            "<a href='/axis'><button"
            " class='gray'>Inicio"
            "</button></a>"
        )
        self._html(
            200,
            _page("AXIS - Abogado", body),
        )

    def _screen_police(self) -> None:
        store = type(self).store
        incidents = store.list_incidents()
        items = ""
        for i in incidents:
            doc = i.get("sealed_doc") or "-"
            items = (
                items
                + "<li>• "
                + i["incident_id"]
                + " — "
                + i["description"]
                + " <small>evidencia: "
                + doc
                + "</small></li>"
            )
        if not items:
            items = (
                "<li>Sin incidentes"
                " reportados</li>"
            )
        body = (
            "<h1>🚓 Seguridad</h1>"
            "<h2>Reportar incidente"
            " (evidencia sellada en la"
            " Red)</h2>"
            "<div class='card'>"
            "<form method='POST'"
            " action='/axis/incident'>"
            "<input name='police_account'"
            " placeholder='Mi ID (AX-...)'>"
            "<input name='description'"
            " placeholder='Descripcion del"
            " incidente'>"
            "<button>Reportar y sellar"
            "</button>"
            "</form></div>"
            "<h2>Incidentes con evidencia"
            " verificable</h2>"
            f"<ul>{items}</ul>"
            "<a href='/axis'><button"
            " class='gray'>Inicio"
            "</button></a>"
        )
        self._html(
            200,
            _page("AXIS - Seguridad", body),
        )

    def _screen_government(self) -> None:
        store = type(self).store
        incidents = store.list_incidents()
        body = (
            "<h1>🏛️ AXIS — Vista"
            " Gobierno</h1>"
            "<h2>Incidentes de seguridad"
            " (con evidencia verificable)"
            "</h2>"
            "<div class='card'>"
            + str(len(incidents))
            + " incidentes sellados"
            + "</div>"
            "<a href='/axis'><button"
            " class='gray'>Inicio"
            "</button></a>"
        )
        self._html(
            200,
            _page("AXIS - Gobierno", body),
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


class AxisServer(ThreadingHTTPServer):
    daemon_threads = True
    allow_reuse_address = True

    def __init__(
        self, address: tuple[str, int]
    ) -> None:
        super().__init__(
            address, AxisApiHandler
        )

    @property
    def bound_port(self) -> int:
        return int(
            self.server_address[1]
        )


def serve_axis(
    store: AxisStore,
    client: NetworkClient,
    *,
    host: str = "127.0.0.1",
    port: int = 0,
) -> AxisServer:
    AxisApiHandler.store = store
    AxisApiHandler.link = AxisLink(client)
    return AxisServer((host, port))
