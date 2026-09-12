"""SEMILLA HTTP surface (role screens + tutor)."""
from __future__ import annotations

import json
import uuid
from http.server import (
    BaseHTTPRequestHandler,
    ThreadingHTTPServer,
)
from typing import Any, ClassVar
from urllib.parse import urlparse

from apps.semilla.infrastructure.persistence.semilla_store import (
    ROLES,
    SemillaStore,
)
from apps.semilla.infrastructure.network.network_client import (
    NetworkClient,
)
from apps.semilla.services.semilla_link import SemillaLink
from apps.semilla.services.tutor import Tutor

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
    ".big{font-size:1.6rem;font-weight:bold;"
    "color:#58a6ff}"
    ".alert{background:#2d1216;border:1px solid"
    " #da3633;border-radius:8px;padding:10px;"
    "margin:8px 0}"
    ".star{background:#2d2a12;border:1px solid"
    " #d29922;border-radius:8px;padding:10px;"
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


class SemillaApiHandler(
    BaseHTTPRequestHandler
):
    store: ClassVar[SemillaStore]
    link: ClassVar[SemillaLink]
    tutor: ClassVar[Tutor] = Tutor()

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
        if segments[:1] != ["semilla"]:
            self._html(
                404,
                _page(
                    "404",
                    "<h1>Fuera de"
                    " SEMILLA</h1>",
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
        tutor = type(self).tutor
        if not s or s == ["home"]:
            self._home()
            return
        if s[0] == "alumno":
            account_id = (
                s[1] if len(s) > 1 else ""
            )
            row = store.get_account(
                account_id
            )
            grades = store.grades_of(
                student_account=(
                    account_id
                )
            )
            average = store.average_of(
                student_account=(
                    account_id
                )
            )
            attendance = (
                store.attendance_rate(
                    student_account=(
                        account_id
                    )
                )
            )
            eligibility = (
                tutor.scholarship_eligibility(
                    average=average,
                    attendance=(
                        attendance
                    ),
                )
            )
            avg_text = (
                f"{average:.1f}"
                if average is not None
                else "sin notas"
            )
            grades_html = "".join(
                "<li>• "
                + g["subject"]
                + ": "
                + str(g["score"])
                + "</li>"
                for g in grades
            )
            if not grades_html:
                grades_html = (
                    "<li>Sin notas aun"
                    "</li>"
                )
            star = ""
            if eligibility[
                "eligible"
            ] and not store.has_scholarship(
                student_account=(
                    account_id
                )
            ):
                store.grant_scholarship(
                    scholarship_id=(
                        "BEC-"
                        + uuid.uuid4()
                        .hex[:10]
                    ),
                    student_account=(
                        account_id
                    ),
                    reason=str(
                        eligibility[
                            "reason"
                        ]
                    ),
                )
            if store.has_scholarship(
                student_account=(
                    account_id
                )
            ):
                star = (
                    "<div class='star'>🎓"
                    " ¡BECA OTORGADA!</div>"
                )
            body = (
                "<h1>🌱 Mi Escuela — "
                + str(row.get("name"))
                + "</h1>"
                "<p>"
                + str(row.get("grade")
                      or "estudiante")
                + " · "
                + str(
                    row.get("school")
                    or "escuela"
                )
                + "</p>"
                "<div class='card'>"
                "<span class='big'>"
                + avg_text
                + "</span> promedio"
                "</div>"
                "<div class='star'>"
                + tutor.stimulus(
                    mood="feliz"
                )["message"]
                + "</div>"
                "<h2>Mis notas</h2><ul>"
                + grades_html
                + "</ul>"
                + star
                + "<a href='/semilla'>"
                "<button class='gray'>"
                "Inicio</button></a>"
            )
            self._html(
                200,
                _page(
                    "SEMILLA - Alumno", body
                ),
            )
            return
        if s[0] == "profesor":
            account_id = (
                s[1] if len(s) > 1 else ""
            )
            row = store.get_account(
                account_id
            )
            students = store.list_by_role(
                role="alumno",
                school=row.get("school"),
            )
            alerts = (
                store.welfare_alerts()
            )
            students_html = ""
            for st in students:
                average = (
                    store.average_of(
                        student_account=(
                            st[
                                "account_id"
                            ]
                        )
                    )
                )
                avg_text = (
                    f"{average:.1f}"
                    if average is not None
                    else "-"
                )
                students_html = (
                    students_html
                    + "<li>• "
                    + str(st["name"])
                    + " — promedio: "
                    + avg_text
                    + "</li>"
                )
            if not students_html:
                students_html = (
                    "<li>Sin alumnos"
                    " registrados</li>"
                )
            alerts_html = "".join(
                "<div class='alert'>⚠️ "
                + a["student"]
                + ": "
                + a["mood"]
                + " - avisar a familia/"
                "profesor</div>"
                for a in alerts
            )
            body = (
                "<h1>👨‍🏫 Panel Profesor — "
                + str(row.get("name"))
                + "</h1>"
                "<p>Escuela: "
                + str(
                    row.get("school")
                    or "general"
                )
                + "</p>"
                "<h2>Mis alumnos</h2><ul>"
                + students_html
                + "</ul>"
                "<h2>Alertas de bienestar"
                " (IA)</h2>"
                + (alerts_html or
                   "<p>Sin alertas 🌈</p>")
                + "<a href='/semilla'>"
                "<button class='gray'>"
                "Inicio</button></a>"
            )
            self._html(
                200,
                _page(
                    "SEMILLA - Profesor",
                    body,
                ),
            )
            return
        if s[0] == "retos" and len(s) > 1:
            self._screen_retos(s[1])
            return
        if s[0] == "talentos" and len(s) > 1:
            self._screen_talentos(s[1])
            return
        if s[0] == "mensajes" and len(s) > 1:
            self._screen_mensajes(s[1])
            return
        if s[0] == "institucion":
            account_id = (
                s[1] if len(s) > 1 else ""
            )
            row = store.get_account(
                account_id
            )
            summary = store.summary(
                school=row.get("school")
            )
            body = (
                "<h1>🏫 "
                + str(row.get("name"))
                + "</h1>"
                "<div class='card'>"
                "<span class='big'>"
                + str(summary["students"])
                + "</span> alumnos · "
                "<span class='big'>"
                + str(summary["teachers"])
                + "</span> profesores"
                "</div>"
                "<a href='/semilla'>"
                "<button class='gray'>"
                "Inicio</button></a>"
            )
            self._html(
                200,
                _page(
                    "SEMILLA - Institucion",
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
        if s == ["register"]:
            name = self._req(doc, "name")
            role = str(
                doc.get("role", "alumno")
            )
            if role not in ROLES:
                raise ValueError(
                    f"unknown role:"
                    f" {role}"
                )
            school = doc.get("school")
            school = (
                str(school)
                if school is not None
                else None
            )
            grade = doc.get("grade")
            grade = (
                str(grade)
                if grade is not None
                else None
            )
            account_id = (
                "SEM-"
                + uuid.uuid4().hex[:12]
            )
            zid: str | None = None
            if role == "alumno":
                ok, data, _error = (
                    link.register_person(
                        name
                    )
                )
                if (
                    ok
                    and data is not None
                ):
                    zid = str(
                        data.get("zid")
                    )
                    link.record_milestone(
                        zid,
                        "inscripcion",
                        name,
                    )
            store.add_account(
                account_id=account_id,
                zid=zid,
                name=name,
                role=role,
                school=school,
                grade=grade,
            )
            self._html(
                200,
                _page(
                    "Bienvenido a SEMILLA",
                    "<h1>Cuenta creada"
                    "</h1>"
                    "<p>Tu ID:"
                    f" <b>{account_id}"
                    "</b></p>"
                    "<a href='/semilla/"
                    f"{role}/{account_id}'>"
                    "<button>Ir a mi panel"
                    "</button></a>"
                ),
            )
            return
        if s == ["grade"]:
            student_account = self._req(
                doc, "student_account"
            )
            teacher_account = self._req(
                doc, "teacher_account"
            )
            row = store.add_grade(
                grade_id=(
                    "NOT-"
                    + uuid.uuid4().hex[:10]
                ),
                student_account=(
                    student_account
                ),
                subject=self._req(
                    doc, "subject"
                ),
                score=float(
                    doc.get("score", 0)
                ),
                teacher_account=(
                    teacher_account
                ),
            )
            self._html(
                200,
                _page(
                    "Nota registrada",
                    "<h1>Nota"
                    " registrada</h1>"
                    f"<p>{row['subject']}:"
                    f" {row['score']}</p>"
                    "<a href='/semilla/"
                    "profesor/"
                    f"{teacher_account}'>"
                    "<button>Volver"
                    "</button></a>",
                ),
            )
            return
        if s == ["challenge"]:
            self._challenge_route(doc)
            return
        if s == ["advance"]:
            self._advance_route(doc)
            return
        if s == ["welfare"]:
            student_account = self._req(
                doc, "student_account"
            )
            mood = self._req(
                doc, "mood"
            )
            result = type(
                self
            ).tutor.stimulus(mood=mood)
            store.add_welfare(
                welfare_id=(
                    "WEL-"
                    + uuid.uuid4().hex[:10]
                ),
                student_account=(
                    student_account
                ),
                mood=mood,
            )
            icon = (
                "🚨"
                if result["critical"]
                else (
                    "⚠️"
                    if result["alert"]
                    else "🌟"
                )
            )
            self._html(
                200,
                _page(
                    "Tutor SEMILLA",
                    "<h1>"
                    + icon
                    + " Tutor SEMILLA"
                    "</h1>"
                    "<p>"
                    + result["message"]
                    + "</p>"
                    + (
                        "<div class='alert'>"
                        "Aviso enviado a:"
                        " "
                        + ", ".join(
                            result[
                                "notify"
                            ]
                        )
                        + "</div>"
                        if result["alert"]
                        else ""
                    )
                    + "<a href='/semilla'>"
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
                        "app": "semilla",
                        "status":
                        "operational",
                    },
                },
            )
            return
        if len(s) == 2 and s[0] == "profile":
            self._api_profile(s[1])
            return
        if len(s) == 2 and s[0] == "messages":
            self._api_messages(s[1])
            return
        if len(s) == 2 and s[0] == "rewards":
            self._api_rewards(s[1])
            return
        if len(s) == 2 and s[0] == "talents":
            self._api_talents(s[1])
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
        if s == ["challenges"]:
            self._api_challenge(doc)
            return
        if s == ["advance"]:
            self._advance_route(doc)
            return
        if s == ["certify"]:
            self._certify_route(doc)
            return
        if s == ["accounts"]:
            account_id = (
                "SEM-"
                + uuid.uuid4().hex[:12]
            )
            row = store.add_account(
                account_id=account_id,
                zid=doc.get("zid"),
                name=self._req(doc, "name"),
                role=self._req(doc, "role"),
                school=doc.get("school"),
                grade=doc.get("grade"),
            )
            self._send(
                201,
                {
                    "ok": True,
                    "data": row,
                },
            )
            return
        if s == ["grades"]:
            row = store.add_grade(
                grade_id=(
                    "NOT-"
                    + uuid.uuid4().hex[:10]
                ),
                student_account=self._req(
                    doc,
                    "student_account",
                ),
                subject=self._req(
                    doc, "subject"
                ),
                score=float(
                    doc.get("score", 0)
                ),
                teacher_account=self._req(
                    doc,
                    "teacher_account",
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

    def _trust_best_effort(self, zid: str | None) -> bool:
        if not zid:
            return False
        try:
            ok, _d, _e = type(self).link.complete_trust(str(zid))
            return bool(ok)
        except Exception:
            return False

    def _network_milestone(
        self, zid: str | None, milestone: str, detail: str,
    ) -> bool:
        if not zid:
            return False
        try:
            ok, _d, _e = type(self).link.record_milestone(
                str(zid), milestone, detail
            )
            return bool(ok)
        except Exception:
            return False

    def _announce_talent(self, student: dict, talent: dict) -> None:
        store = type(self).store
        text = (
            str(student.get("name"))
            + " ha demostrado talento en "
            + str(talent["domain"])
        )
        for profesor in store.list_by_role(
            role="profesor",
            school=student.get("school"),
        ):
            store.add_message(
                message_id="MSG-" + uuid.uuid4().hex[:10],
                recipient=str(profesor["account_id"]),
                text=text,
                student_account=str(student["account_id"]),
            )
        store.add_message(
            message_id="MSG-" + uuid.uuid4().hex[:10],
            recipient="familia",
            text=text,
            student_account=str(student["account_id"]),
        )
        self._network_milestone(
            student.get("zid"),
            "talento",
            str(talent["domain"]),
        )

    def _challenge_flow(self, doc: dict) -> dict:
        store = type(self).store
        tutor = type(self).tutor
        student_account = self._req(doc, "student_account")
        answer = self._req(doc, "answer")
        state = store.get_challenge_state(student_account=student_account)
        domain = str(state["domain"])
        difficulty = int(state["difficulty"])
        correct = tutor.check_answer(
            domain=domain,
            difficulty=difficulty,
            submitted=answer,
        )
        new_difficulty = tutor.adapt_difficulty(
            difficulty=difficulty, correct=correct
        )
        store.record_attempt(
            attempt_id="ATT-" + uuid.uuid4().hex[:10],
            student_account=student_account,
            domain=domain,
            difficulty=difficulty,
            correct=correct,
        )
        store.set_challenge_state(
            student_account=student_account,
            domain=domain,
            difficulty=new_difficulty,
        )
        points_earned = 0
        if correct:
            store.add_reward(
                reward_id="REW-" + uuid.uuid4().hex[:10],
                student_account=student_account,
                kind="reto",
                detail=domain + " nivel " + str(difficulty),
                points=10,
            )
            points_earned = 10
        student = store.get_account(student_account)
        for talent in store.detect_talents(student_account=student_account):
            self._announce_talent(student, talent)
        return {
            "correct": correct,
            "domain": domain,
            "difficulty": new_difficulty,
            "points_earned": points_earned,
            "total_points": store.total_points(student_account=student_account),
        }

    def _challenge_route(self, doc: dict) -> None:
        result = self._challenge_flow(doc)
        if result["correct"]:
            feedback = "Correcto. Nivel ahora: " + str(result["difficulty"])
        else:
            feedback = "Incorrecto. Sigue intentando."
        back_link = (
            "<a href='/semilla/retos/"
            + self._req(doc, "student_account")
            + "'><button>Volver a retos</button></a>"
        )
        self._html(
            200,
            _page(
                "Reto SEMILLA",
                "<h1>Reto SEMILLA</h1>"
                "<p>" + feedback + "</p>"
                "<p>Puntos: " + str(result["total_points"]) + "</p>"
                + back_link
            ),
        )

    def _api_challenge(self, doc: dict) -> None:
        result = self._challenge_flow(doc)
        self._send(200, {"ok": True, "data": result})

    def _advance_route(self, doc: dict) -> None:
        store = type(self).store
        student_account = self._req(doc, "student_account")
        new_grade = self._req(doc, "new_grade")
        student = store.get_account(student_account)
        if student.get("role") != "alumno":
            raise ValueError("only students advance")
        store.update_grade(account_id=student_account, new_grade=new_grade)
        milestone = self._network_milestone(
            student.get("zid"),
            "avance",
            new_grade,
        )
        text = str(student.get("name")) + " avanza a " + new_grade
        store.add_message(
            message_id="MSG-" + uuid.uuid4().hex[:10],
            recipient="familia",
            text=text,
            student_account=student_account,
        )
        for profesor in store.list_by_role(
            role="profesor",
            school=student.get("school"),
        ):
            store.add_message(
                message_id="MSG-" + uuid.uuid4().hex[:10],
                recipient=str(profesor["account_id"]),
                text=text,
                student_account=student_account,
            )
        self._send(
            200,
            {
                "ok": True,
                "data": {
                    "student_account": student_account,
                    "grade": new_grade,
                    "milestone_recorded": bool(milestone),
                },
            },
        )

    def _certify_route(self, doc: dict) -> None:
        store = type(self).store
        student_account = self._req(doc, "student_account")
        teacher_account = self._req(doc, "teacher_account")
        student = store.get_account(student_account)
        teacher = store.get_account(teacher_account)
        if student.get("zid") is None:
            raise ValueError("student has no network ZID")
        if teacher.get("zid") is None:
            ok, data, _e = type(self).link.register_person(
                str(teacher.get("name"))
            )
            if ok and data is not None:
                zid = data.get("zid")
                if zid:
                    store.set_zid(account_id=teacher_account, zid=str(zid))
        teacher = store.get_account(teacher_account)
        talents = store.list_talents(student_account=student_account)
        average = store.average_of(student_account=student_account)
        if not talents and (average is None or average < 8.0):
            raise ValueError("sin merito certifiable")
        self._trust_best_effort(student.get("zid"))
        self._trust_best_effort(teacher.get("zid"))
        ok, data, err = type(self).link.issue_education_credential(
            subject_zid=str(student.get("zid")),
            issuer_zid=str(teacher.get("zid")),
            title="Certificado SEMILLA",
            detail="trayectoria educativa verificada",
        )
        result = {"issued": bool(ok)}
        if ok and data is not None:
            credential_id = data.get("credential_id") or data.get("id")
            if credential_id:
                result["credential_id"] = credential_id
        elif not ok:
            result["error"] = err
        store.add_message(
            message_id="MSG-" + uuid.uuid4().hex[:10],
            recipient="familia",
            text="Certificado educativo emitido para "
            + str(student.get("name")),
            student_account=student_account,
        )
        self._send(200, {"ok": True, "data": result})

    def _screen_retos(self, student_id: str) -> None:
        store = type(self).store
        tutor = type(self).tutor
        student = store.get_account(student_id)
        state = store.get_challenge_state(student_account=student_id)
        challenge = tutor.next_challenge(
            domain=str(state["domain"]),
            difficulty=int(state["difficulty"]),
        )
        options_html = "".join(
            "<option value='" + o + "'>" + o + "</option>"
            for o in challenge["options"]
        )
        attempts = store.attempts_of(student_account=student_id)
        body = (
            "<h1>Retos SEMILLA</h1>"
            "<p>" + str(student.get("name")) + "</p>"
            "<p>Area: " + str(challenge["domain"])
            + " | Nivel: " + str(challenge["difficulty"])
            + " | Intentos: " + str(len(attempts)) + "</p>"
            "<div class='card'>"
            "<form method='POST' action='/semilla/challenge'>"
            "<input type='hidden' name='student_account'"
            " value='" + student_id + "'>"
            "<p><b>" + str(challenge["question"]) + "</b></p>"
            "<select name='answer'>" + options_html + "</select>"
            "<button>Enviar respuesta</button></form></div>"
            "<p><small>El Tutor mide tu respuesta. No resuelve el reto por ti.</small></p>"
            "<a href='/semilla'><button class='gray'>Inicio</button></a>"
        )
        self._html(200, _page("SEMILLA - Retos", body))

    def _screen_talentos(self, student_id: str) -> None:
        store = type(self).store
        tutor = type(self).tutor
        student = store.get_account(student_id)
        for talent in store.detect_talents(student_account=student_id):
            self._announce_talent(student, talent)
        talents = store.list_talents(student_account=student_id)
        grades = store.grades_of(student_account=student_id)
        attendance = store.attendance_rate(student_account=student_id)
        profile = tutor.student_profile(grades=grades, attendance=attendance)
        rows = "".join(
            "<li>- " + str(t["domain"])
            + " (" + str(t["evidence"]) + ")</li>"
            for t in talents
        )
        if not rows:
            rows = "<li>Talento en formacion: sigue intentando</li>"
        state = store.get_challenge_state(student_account=student_id)
        body = (
            "<h1>Talentos detectados</h1>"
            "<p>" + str(student.get("name")) + "</p>"
            "<ul>" + rows + "</ul>"
            "<p>Recomendado: retos de " + str(state["domain"])
            + " nivel " + str(state["difficulty"]) + "</p>"
            "<p>Fortalezas: " + ", ".join(profile["strengths"]) + "</p>"
            "<p>Por reforzar: " + ", ".join(profile["weaknesses"]) + "</p>"
            "<a href='/semilla/retos/" + student_id
            + "'><button>Ir a mis retos</button></a>"
            "<a href='/semilla'><button class='gray'>Inicio</button></a>"
        )
        self._html(200, _page("SEMILLA - Talentos", body))

    def _screen_mensajes(self, recipient_id: str) -> None:
        store = type(self).store
        messages = store.messages_of(recipient=recipient_id)
        rows = "".join(
            "<li>- " + str(m["text"]) + "</li>"
            for m in messages
        )
        if not rows:
            rows = "<li>Sin mensajes todavia</li>"
        body = (
            "<h1>Mensajes</h1>"
            "<ul>" + rows + "</ul>"
            "<a href='/semilla'><button class='gray'>Inicio</button></a>"
        )
        self._html(200, _page("SEMILLA - Mensajes", body))

    def _api_profile(self, account_id: str) -> None:
        store = type(self).store
        student = store.get_account(account_id)
        grades = store.grades_of(student_account=account_id)
        attendance = store.attendance_rate(student_account=account_id)
        profile = type(self).tutor.student_profile(
            grades=grades, attendance=attendance
        )
        profile["student_account"] = account_id
        profile["name"] = str(student.get("name"))
        self._send(200, {"ok": True, "data": profile})

    def _api_messages(self, recipient_id: str) -> None:
        store = type(self).store
        messages = store.messages_of(recipient=recipient_id)
        self._send(
            200,
            {
                "ok": True,
                "data": {
                    "recipient": recipient_id,
                    "messages": list(messages),
                },
            },
        )

    def _api_rewards(self, account_id: str) -> None:
        store = type(self).store
        self._send(
            200,
            {
                "ok": True,
                "data": {
                    "student_account": account_id,
                    "total_points": store.total_points(student_account=account_id),
                    "rewards": list(store.rewards_of(student_account=account_id)),
                },
            },
        )

    def _api_talents(self, account_id: str) -> None:
        store = type(self).store
        self._send(
            200,
            {
                "ok": True,
                "data": {
                    "student_account": account_id,
                    "talents": list(store.list_talents(student_account=account_id)),
                },
            },
        )

    def _home(self) -> None:
        body = (
            "<h1>🌱 SEMILLA</h1>"
            "<p>Educacion con historial"
            " verificado y IA-tutor que"
            " acompaña, no hace trampa.</p>"
            "<h2>Soy alumno</h2>"
            "<div class='card'>"
            "<form method='POST'"
            " action='/semilla/register'>"
            "<input type='hidden'"
            " name='role' value="
            "'alumno'>"
            "<input name='name'"
            " placeholder='Mi nombre'>"
            "<input name='school'"
            " placeholder='Mi escuela'>"
            "<select name='grade'>"
            "<option value='prekinder'>"
            "Prekinder</option>"
            "<option value='kinder'>"
            "Kinder</option>"
            "<option value='primaria'>"
            "Primaria</option>"
            "<option value='secundaria'>"
            "Secundaria</option>"
            "<option value="
            "'universidad'>"
            "Universidad</option>"
            "</select>"
            "<button>Registrarme"
            "</button>"
            "</form></div>"
            "<h2>Soy profesor</h2>"
            "<div class='card'>"
            "<form method='POST'"
            " action='/semilla/register'>"
            "<input type='hidden'"
            " name='role' value="
            "'profesor'>"
            "<input name='name'"
            " placeholder='Mi nombre'>"
            "<input name='school'"
            " placeholder='Mi escuela'>"
            "<button>Registrarme"
            "</button>"
            "</form></div>"
            "<h2>Soy institucion</h2>"
            "<div class='card'>"
            "<form method='POST'"
            " action='/semilla/register'>"
            "<input type='hidden'"
            " name='role' value="
            "'institucion'>"
            "<input name='name'"
            " placeholder='Nombre del"
            " centro escolar'>"
            "<button>Registrarme"
            "</button>"
            "</form></div>"
        )
        self._html(
            200, _page("SEMILLA", body)
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


class SemillaServer(ThreadingHTTPServer):
    daemon_threads = True
    allow_reuse_address = True

    def __init__(
        self, address: tuple[str, int]
    ) -> None:
        super().__init__(
            address, SemillaApiHandler
        )

    @property
    def bound_port(self) -> int:
        return int(
            self.server_address[1]
        )


def serve_semilla(
    store: SemillaStore,
    client: NetworkClient,
    *,
    host: str = "127.0.0.1",
    port: int = 0,
) -> SemillaServer:
    SemillaApiHandler.store = store
    SemillaApiHandler.link = SemillaLink(
        client
    )
    return SemillaServer((host, port))
