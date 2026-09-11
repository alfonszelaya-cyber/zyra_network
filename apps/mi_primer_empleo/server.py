"""MPE HTTP server - bidirectional employment."""
from __future__ import annotations

import json
import uuid
from http.server import (
    BaseHTTPRequestHandler,
    ThreadingHTTPServer,
)
from urllib.parse import parse_qs

from apps.mi_primer_empleo.infrastructure.persistence.mpe_store import (
    MpeStore,
)
from apps.mi_primer_empleo.services.mpe_link import (
    MpeLink,
)


def _new_account_id() -> str:
    return "MPE-" + uuid.uuid4().hex[:12]


def _new_job_id() -> str:
    return "JOB-" + uuid.uuid4().hex[:10]


def _new_proposal_id() -> str:
    return "PROP-" + uuid.uuid4().hex[:10]


def _new_hire_id() -> str:
    return "HIR-" + uuid.uuid4().hex[:10]


def _new_application_id() -> str:
    return "APP-" + uuid.uuid4().hex[:10]


def _find_zid(doc):
    if isinstance(doc, dict):
        for key, value in (
            doc.items()
        ):
            if (
                str(key).lower()
                == "zid"
                and isinstance(
                    value, str
                )
                and value.startswith(
                    "ZID-"
                )
            ):
                return value
        for value in doc.values():
            found = _find_zid(value)
            if found is not None:
                return found
    elif isinstance(doc, list):
        for item in doc:
            found = _find_zid(item)
            if found is not None:
                return found
    return None


def _find_credential_id(doc):
    if isinstance(doc, dict):
        for key, value in (
            doc.items()
        ):
            key_lower = str(
                key
            ).lower()
            if (
                (
                    "credential"
                    in key_lower
                )
                or key_lower == "id"
            ) and isinstance(
                value, str
            ) and value:
                return value
        for value in doc.values():
            found = (
                _find_credential_id(
                    value
                )
            )
            if found is not None:
                return found
    elif isinstance(doc, list):
        for item in doc:
            found = (
                _find_credential_id(
                    item
                )
            )
            if found is not None:
                return found
    return None


class MpeApiHandler(BaseHTTPRequestHandler):
    store: MpeStore
    link: MpeLink

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

    def _ok(self, data) -> None:
        self._send_json(
            200,
            {"ok": True, "data": data},
        )

    def _api_error(
        self,
        status: int,
        message: str,
    ) -> None:
        self._send_json(
            status,
            {
                "ok": False,
                "error": message,
            },
        )

    def _html_error(
        self,
        status: int,
        message: str,
    ) -> None:
        self._send_html(
            status,
            "<html><body><h1>MPE"
            "</h1><p>Error: "
            + message
            + "</p></body></html>",
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
        return self.rfile.read(
            length
        )

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

    def _split_path(self) -> tuple[
        str, dict,
    ]:
        raw = self.path
        if "?" in raw:
            path, qs = raw.split(
                "?", 1
            )
            query = {
                k: v[0]
                for k, v in parse_qs(
                    qs
                ).items()
                if v
            }
        else:
            path = raw
            query = {}
        return path, query

    def _trust_best_effort(
        self, zid: str | None,
    ) -> bool:
        if not zid:
            return False
        try:
            ok, _d, _e = (
                self.link.complete_trust(
                    zid
                )
            )
            return bool(ok)
        except Exception:
            return False

    def _network_on_hire(
        self,
        job_id: str,
        worker_account: str,
    ) -> dict:
        result: dict = {
            "credential": {
                "issued": False,
            },
            "history_recorded":
            False,
            "trust_completed":
            False,
        }
        try:
            status = (
                self.store.job_status(
                    job_id=job_id
                )
            )
            worker = (
                self.store.get_account(
                    worker_account
                )
            )
            worker_zid = worker.get(
                "zid"
            )
            company = (
                self.store.get_account(
                    str(
                        status[
                            "company_account"
                        ]
                    )
                )
            )
            company_zid = (
                company.get("zid")
            )
            trust_ok = (
                self._trust_best_effort(
                    company_zid
                )
                and self
                ._trust_best_effort(
                    worker_zid
                )
            )
            result[
                "trust_completed"
            ] = bool(trust_ok)
            if (
                worker_zid
                and company_zid
            ):
                ok, data, err = (
                    self.link
                    .issue_employment_credential(
                        subject_zid=str(
                            worker_zid
                        ),
                        issuer_zid=str(
                            company_zid
                        ),
                        title=str(
                            status[
                                "title"
                            ]
                        ),
                        detail=(
                            "contratacion"
                            " registrada en"
                            " MPE"
                        ),
                    )
                )
                credential = {
                    "issued": bool(
                        ok
                    ),
                }
                if (
                    ok
                    and isinstance(
                        data, dict
                    )
                ):
                    credential_id = (
                        _find_credential_id(
                            data
                        )
                    )
                    if (
                        credential_id
                    ):
                        credential[
                            "credential_id"
                        ] = (
                            credential_id
                        )
                elif not ok:
                    credential[
                        "error"
                    ] = err
                result[
                    "credential"
                ] = credential
            if worker_zid:
                hok, _hd, _he = (
                    self.link
                    .record_work_event(
                        str(
                            worker_zid
                        ),
                        "hired",
                        str(
                            status[
                                "title"
                            ]
                        ),
                    )
                )
                result[
                    "history_recorded"
                ] = bool(hok)
        except Exception:
            pass
        return result

    def _network_on_leave(
        self,
        job_id: str,
        worker_account: str,
    ) -> bool:
        try:
            worker = (
                self.store.get_account(
                    worker_account
                )
            )
            worker_zid = worker.get(
                "zid"
            )
            if not worker_zid:
                return False
            status = (
                self.store.job_status(
                    job_id=job_id
                )
            )
            hok, _hd, _he = (
                self.link.record_work_event(
                    str(worker_zid),
                    "left",
                    str(
                        status["title"]
                    ),
                )
            )
            return bool(hok)
        except Exception:
            return False

    def do_GET(self) -> None:
        path, query = (
            self._split_path()
        )
        try:
            if path in (
                "/",
                "/mpe",
                "/mpe/home",
            ):
                self._send_html(
                    200,
                    self._home(),
                )
                return
            if path == "/mpe/jobs":
                self._send_html(
                    200,
                    self._jobs_html(),
                )
                return
            if path == (
                "/mpe/government/summary"
            ):
                self._send_html(
                    200,
                    self._gov_html(),
                )
                return
            if path.startswith(
                "/mpe/trabajador/"
            ):
                account_id = path.split(
                    "/mpe/trabajador/",
                    1,
                )[1]
                self._worker_panel(
                    account_id
                )
                return
            if path.startswith(
                "/mpe/empresa/"
            ):
                account_id = path.split(
                    "/mpe/empresa/",
                    1,
                )[1]
                self._company_panel(
                    account_id
                )
                return
            if path == (
                "/mpe/api/health"
            ):
                self._ok(
                    {
                        "app": "mpe",
                        "status": "ok",
                    }
                )
                return
            if path == (
                "/mpe/api/summary"
            ):
                self._ok(
                    self.store.summary()
                )
                return
            if path == (
                "/mpe/api/jobs"
            ):
                jobs = []
                for job in (
                    self.store.list_jobs()
                ):
                    jobs.append(
                        self.store
                        .job_status(
                            job_id=str(
                                job[
                                    "job_id"
                                ]
                            )
                        )
                    )
                self._ok(
                    {"jobs": jobs}
                )
                return
            if path == (
                "/mpe/api/workers"
            ):
                profession = query.get(
                    "profession"
                )
                workers = (
                    self.store
                    .list_workers(
                        profession=(
                            profession
                        )
                    )
                )
                self._ok(
                    {
                        "workers": list(
                            workers
                        )
                    }
                )
                return
            if path.startswith(
                "/mpe/api/job/"
            ):
                job_id = path.split(
                    "/mpe/api/job/",
                    1,
                )[1]
                self._ok(
                    self.store.job_status(
                        job_id=job_id
                    )
                )
                return
            if path == (
                "/mpe/api/proposals"
            ):
                proposals = (
                    self.store
                    .list_proposals(
                        worker_account=(
                            query.get(
                                "worker"
                            )
                        ),
                        job_id=(
                            query.get(
                                "job"
                            )
                        ),
                        status=(
                            query.get(
                                "status",
                                "pending",
                            )
                        ),
                    )
                )
                self._ok(
                    {
                        "proposals": list(
                            proposals
                        )
                    }
                )
                return
            if path == (
                "/mpe/api/notifications"
            ):
                self._notifications(
                    query
                )
                return
            self._api_error(
                404,
                "unknown path: "
                + path,
            )
        except LookupError as exc:
            self._api_error(
                404, str(exc)
            )
        except ValueError as exc:
            self._api_error(
                400, str(exc)
            )
        except Exception:
            self._api_error(
                500, "server error"
            )

    def _notifications(
        self, query: dict,
    ) -> None:
        worker = query.get("worker")
        items: list[dict] = []
        if worker:
            for proposal in (
                self.store
                .list_proposals(
                    worker_account=(
                        worker
                    ),
                    status="pending",
                )
            ):
                items.append(
                    {
                        "kind":
                        "proposal",
                        "message": (
                            "Una empresa"
                            " quiere"
                            " contratarte"
                        ),
                        "proposal_id": (
                            proposal[
                                "proposal_id"
                            ]
                        ),
                        "job_id": (
                            proposal[
                                "job_id"
                            ]
                        ),
                    }
                )
            account = (
                self.store.get_account(
                    worker
                )
            )
            for job in (
                self.store.list_jobs(
                    profession=account.get(
                        "profession"
                    )
                )
            ):
                items.append(
                    {
                        "kind":
                        "job_opportunity",
                        "job_id": job[
                            "job_id"
                        ],
                        "title": job[
                            "title"
                        ],
                    }
                )
        self._ok(
            {
                "worker": worker,
                "notifications": (
                    items
                ),
            }
        )

    def _home(self) -> str:
        return (
            "<html><head>"
            "<title>MPE</title></head>"
            "<body><h1>MPE - Mi Primer"
            " Empleo</h1>"
            "<p>El trabajo busca al"
            " trabajador.</p>"
            "<ul>"
            "<li>POST /mpe/register"
            " (form)</li>"
            "<li>POST /mpe/job"
            " (form)</li>"
            "<li>POST /mpe/apply"
            " (form)</li>"
            "<li>POST /mpe/proposal"
            " (form)</li>"
            "<li>POST"
            " /mpe/proposal-decide"
            " (form)</li>"
            "<li>POST /mpe/hire"
            " (form)</li>"
            "<li>POST /mpe/leave"
            " (form)</li>"
            "<li>GET"
            " /mpe/api/notifications"
            " ?worker=</li>"
            "<li>GET"
            " /mpe/api/summary</li>"
            "</ul></body></html>"
        )

    def _jobs_html(self) -> str:
        html = (
            "<html><body><h1>Vacantes"
            " abiertas</h1><ul>"
        )
        for job in (
            self.store.list_jobs()
        ):
            status = (
                self.store.job_status(
                    job_id=str(
                        job["job_id"]
                    )
                )
            )
            html += (
                "<li>"
                + str(
                    status["job_id"]
                )
                + " | "
                + str(status["title"])
                + " | contratados "
                + str(status["hired"])
                + "/"
                + str(
                    status["openings"]
                )
                + " | quedan "
                + str(
                    status["remaining"]
                )
                + "</li>"
            )
        html += (
            "</ul></body></html>"
        )
        return html

    def _gov_html(self) -> str:
        data = self.store.summary()
        return (
            "<html><body><h1>Resumen"
            " gobierno</h1>"
            "<p>cuentas: "
            + str(
                data["accounts_total"]
            )
            + "</p>"
            "<p>verificadas: "
            + str(
                data[
                    "accounts_verified"
                ]
            )
            + "</p>"
            "<p>vacantes abiertas: "
            + str(data["open_jobs"])
            + "</p>"
            "<p>aplicaciones: "
            + str(
                data[
                    "applications_total"
                ]
            )
            + "</p>"
            "<p>contrataciones"
            " activas: "
            + str(data["hires_total"])
            + "</p>"
            "<p>propuestas pendientes:"
            " "
            + str(
                data[
                    "proposals_pending"
                ]
            )
            + "</p></body></html>"
        )

    def _worker_panel(
        self, account_id: str,
    ) -> None:
        try:
            account = (
                self.store.get_account(
                    account_id
                )
            )
        except LookupError:
            self._html_error(
                404,
                "cuenta no existe",
            )
            return
        html = (
            "<html><body><h1>Panel"
            " trabajador</h1>"
            "<p>"
            + str(account["name"])
            + " ("
            + str(
                account["profession"]
            )
            + ")</p>"
            "<h2>Propuestas"
            " recibidas</h2><ul>"
        )
        proposals = (
            self.store.list_proposals(
                worker_account=(
                    account_id
                ),
                status="pending",
            )
        )
        for proposal in proposals:
            html += (
                "<li>Una empresa quiere"
                " contratarte (propuesta "
                + str(
                    proposal[
                        "proposal_id"
                    ]
                )
                + " para vacante "
                + str(proposal["job_id"])
                + ")"
                + " <form method='POST'"
                + " action="
                + "'/mpe/proposal-decide'>"
                + "<input type='hidden'"
                + " name='proposal_id'"
                + " value='"
                + str(
                    proposal[
                        "proposal_id"
                    ]
                )
                + "'>"
                + "<button name='decision'"
                + " value='aceptar'>"
                + "Aceptar</button>"
                + "<button name='decision'"
                + " value='rechazar'>"
                + "Rechazar</button>"
                + "</form></li>"
            )
        html += (
            "</ul><h2>Vacantes para ti"
            "</h2><ul>"
        )
        for job in (
            self.store.list_jobs(
                profession=account.get(
                    "profession"
                )
            )
        ):
            html += (
                "<li>"
                + str(job["title"])
                + " ("
                + str(job["job_id"])
                + ")</li>"
            )
        html += "</ul></body></html>"
        self._send_html(200, html)

    def _company_panel(
        self, account_id: str,
    ) -> None:
        try:
            account = (
                self.store.get_account(
                    account_id
                )
            )
        except LookupError:
            self._html_error(
                404,
                "cuenta no existe",
            )
            return
        if account.get("role") != (
            "empresa"
        ):
            self._html_error(
                400,
                "no es empresa",
            )
            return
        html = (
            "<html><body><h1>Panel"
            " empresa</h1><p>"
            + str(account["name"])
            + "</p><h2>Tus vacantes"
            "</h2><ul>"
        )
        for job in (
            self.store.list_company_jobs(
                company_account=(
                    account_id
                )
            )
        ):
            status = (
                self.store.job_status(
                    job_id=str(
                        job["job_id"]
                    )
                )
            )
            html += (
                "<li>"
                + str(status["title"])
                + " | "
                + str(status["status"])
                + " | contratados "
                + str(status["hired"])
                + "/"
                + str(
                    status["openings"]
                )
                + " | quedan "
                + str(
                    status["remaining"]
                )
                + "</li>"
            )
        html += (
            "</ul><h2>Trabajadores"
            " disponibles</h2><ul>"
        )
        for worker in (
            self.store.list_workers()
        ):
            html += (
                "<li>"
                + str(worker["name"])
                + " ("
                + str(
                    worker[
                        "profession"
                    ]
                )
                + ")</li>"
            )
        html += "</ul></body></html>"
        self._send_html(200, html)

    def do_POST(self) -> None:
        path, _query = (
            self._split_path()
        )
        try:
            if path == "/mpe/register":
                self._register()
                return
            if path == "/mpe/job":
                self._post_job_form()
                return
            if path == "/mpe/apply":
                self._apply_form()
                return
            if path == "/mpe/proposal":
                self._proposal_form()
                return
            if path == (
                "/mpe/proposal-decide"
            ):
                self._decide_form()
                return
            if path == "/mpe/hire":
                self._hire_form()
                return
            if path == "/mpe/leave":
                self._leave_form()
                return
            if path == (
                "/mpe/api/accounts"
            ):
                self._api_account()
                return
            if path == "/mpe/api/jobs":
                self._api_job()
                return
            if path == (
                "/mpe/api/proposals"
            ):
                self._api_proposal()
                return
            if path == (
                "/mpe/api/proposals"
                "/decide"
            ):
                self._api_decide()
                return
            if path == (
                "/mpe/api/hires"
            ):
                self._api_hire()
                return
            if path == (
                "/mpe/api/leave"
            ):
                self._api_leave()
                return
            self._api_error(
                404,
                "unknown path: "
                + path,
            )
        except LookupError as exc:
            self._api_error(
                404, str(exc)
            )
        except (
            ValueError,
            PermissionError,
        ) as exc:
            self._api_error(
                400, str(exc)
            )
        except Exception:
            self._api_error(
                500, "server error"
            )

    def _register(self) -> None:
        form = self._read_form()
        role = self._form_value(
            form, "role"
        )
        name = self._form_value(
            form, "name"
        )
        profession = self._form_value(
            form, "profession"
        )
        if role not in (
            "trabajador",
            "empresa",
        ):
            self._html_error(
                400, "role invalido"
            )
            return
        if not name:
            self._html_error(
                400, "name requerido"
            )
            return
        zid = None
        if role == "trabajador":
            ok, data, _err = (
                self.link.register_user(
                    name
                )
            )
        else:
            ok, data, _err = (
                self.link
                .register_company(
                    name
                )
            )
        if ok and data is not None:
            zid = _find_zid(data)
        account_id = _new_account_id()
        self.store.add_account(
            account_id=account_id,
            zid=zid,
            name=name,
            role=role,
            profession=(
                profession or None
            ),
        )
        if zid is not None:
            self._trust_best_effort(
                zid
            )
            self.store.mark_verified(
                account_id=account_id
            )
        html = (
            "<html><body><h1>MPE</h1>"
            "<p>Cuenta registrada</p>"
            "<p>id: "
            + account_id
            + "</p><p>zid: "
            + str(zid)
            + "</p></body></html>"
        )
        self._send_html(200, html)

    def _post_job_form(self) -> None:
        form = self._read_form()
        job = self.store.post_job(
            job_id=_new_job_id(),
            company_account=(
                self._form_value(
                    form,
                    "company_account",
                )
            ),
            title=self._form_value(
                form, "title"
            ),
            profession=(
                self._form_value(
                    form,
                    "profession",
                )
            ),
            openings=int(
                self._form_value(
                    form, "openings"
                )
                or "1"
            ),
        )
        self._send_html(
            200,
            "<html><body><h1>MPE</h1>"
            "<p>Vacante publicada</p>"
            "<p>job: "
            + str(job["job_id"])
            + "</p></body></html>",
        )

    def _apply_form(self) -> None:
        form = self._read_form()
        self.store.apply(
            application_id=(
                _new_application_id()
            ),
            job_id=self._form_value(
                form, "job_id"
            ),
            worker_account=(
                self._form_value(
                    form,
                    "worker_account",
                )
            ),
        )
        self._send_html(
            200,
            "<html><body><h1>MPE</h1>"
            "<p>Aplicacion enviada"
            "</p></body></html>",
        )

    def _proposal_form(self) -> None:
        form = self._read_form()
        proposal = (
            self.store.create_proposal(
                proposal_id=(
                    _new_proposal_id()
                ),
                job_id=(
                    self._form_value(
                        form, "job_id"
                    )
                ),
                company_account=(
                    self._form_value(
                        form,
                        "company_account",
                    )
                ),
                worker_account=(
                    self._form_value(
                        form,
                        "worker_account",
                    )
                ),
            )
        )
        self._send_html(
            200,
            "<html><body><h1>MPE</h1>"
            "<p>Propuesta enviada</p>"
            "<p>propuesta: "
            + str(
                proposal[
                    "proposal_id"
                ]
            )
            + "</p></body></html>",
        )

    def _decide_form(self) -> None:
        form = self._read_form()
        decision = self._form_value(
            form, "decision"
        )
        if decision not in (
            "aceptar",
            "rechazar",
        ):
            self._html_error(
                400,
                "decision invalida",
            )
            return
        result = (
            self.store.decide_proposal(
                proposal_id=(
                    self._form_value(
                        form,
                        "proposal_id",
                    )
                ),
                accepted=(
                    decision
                    == "aceptar"
                ),
            )
        )
        if result["status"] == (
            "accepted"
        ):
            net = (
                self._network_on_hire(
                    str(
                        result["job_id"]
                    ),
                    str(
                        result[
                            "worker_account"
                        ]
                    ),
                )
            )
            self._send_html(
                200,
                "<html><body><h1>MPE"
                "</h1><p>Contratado</p>"
                "<p>contratados: "
                + str(
                    result["hire"][
                        "hired"
                    ]
                )
                + " | quedan: "
                + str(
                    result["hire"][
                        "remaining"
                    ]
                )
                + "</p>"
                "<p>credencial: "
                + str(
                    net["credential"][
                        "issued"
                    ]
                )
                + "</p></body></html>",
            )
            return
        self._send_html(
            200,
            "<html><body><h1>MPE</h1>"
            "<p>Propuesta rechazada"
            "</p></body></html>",
        )

    def _hire_form(self) -> None:
        form = self._read_form()
        job_id = self._form_value(
            form, "job_id"
        )
        worker_account = (
            self._form_value(
                form, "worker_account"
            )
        )
        hire = self.store.hire_worker(
            hire_id=_new_hire_id(),
            job_id=job_id,
            worker_account=(
                worker_account
            ),
        )
        net = self._network_on_hire(
            job_id, worker_account
        )
        self._send_html(
            200,
            "<html><body><h1>MPE</h1>"
            "<p>Contratado</p>"
            "<p>contratados: "
            + str(hire["hired"])
            + " | quedan: "
            + str(hire["remaining"])
            + " | estado: "
            + str(hire["job_status"])
            + "</p>"
            "<p>credencial: "
            + str(
                net["credential"][
                    "issued"
                ]
            )
            + "</p></body></html>",
        )

    def _leave_form(self) -> None:
        form = self._read_form()
        job_id = self._form_value(
            form, "job_id"
        )
        worker_account = (
            self._form_value(
                form, "worker_account"
            )
        )
        result = (
            self.store.worker_leaves(
                job_id=job_id,
                worker_account=(
                    worker_account
                ),
            )
        )
        self._network_on_leave(
            job_id, worker_account
        )
        self._send_html(
            200,
            "<html><body><h1>MPE</h1>"
            "<p>Abandono registrado"
            "</p><p>reabierta: "
            + str(result["reopened"])
            + " | quedan: "
            + str(result["remaining"])
            + "</p></body></html>",
        )

    def _api_account(self) -> None:
        doc = self._read_json()
        if doc is None:
            self._api_error(
                400, "invalid JSON"
            )
            return
        role = str(
            doc.get("role", "")
        )
        name = str(
            doc.get("name", "")
        )
        profession = doc.get(
            "profession"
        )
        zid = None
        if role == "trabajador":
            ok, data, _err = (
                self.link.register_user(
                    name
                )
            )
        elif role == "empresa":
            ok, data, _err = (
                self.link
                .register_company(
                    name
                )
            )
        else:
            self._api_error(
                400, "role invalido"
            )
            return
        if ok and data is not None:
            zid = _find_zid(data)
        account_id = _new_account_id()
        account = (
            self.store.add_account(
                account_id=account_id,
                zid=zid,
                name=name,
                role=role,
                profession=(
                    str(profession)
                    if profession
                    else None
                ),
            )
        )
        if zid is not None:
            self._trust_best_effort(
                zid
            )
            self.store.mark_verified(
                account_id=account_id
            )
        self._ok(account)

    def _api_job(self) -> None:
        doc = self._read_json()
        if doc is None:
            self._api_error(
                400, "invalid JSON"
            )
            return
        job = self.store.post_job(
            job_id=_new_job_id(),
            company_account=str(
                doc.get(
                    "company_account",
                    "",
                )
            ),
            title=str(
                doc.get("title", "")
            ),
            profession=str(
                doc.get(
                    "profession", ""
                )
            ),
            openings=int(
                doc.get("openings", 1)
            ),
        )
        self._ok(job)

    def _api_proposal(self) -> None:
        doc = self._read_json()
        if doc is None:
            self._api_error(
                400, "invalid JSON"
            )
            return
        proposal = (
            self.store.create_proposal(
                proposal_id=(
                    _new_proposal_id()
                ),
                job_id=str(
                    doc.get(
                        "job_id", ""
                    )
                ),
                company_account=str(
                    doc.get(
                        "company_account",
                        "",
                    )
                ),
                worker_account=str(
                    doc.get(
                        "worker_account",
                        "",
                    )
                ),
            )
        )
        self._ok(proposal)

    def _api_decide(self) -> None:
        doc = self._read_json()
        if doc is None:
            self._api_error(
                400, "invalid JSON"
            )
            return
        decision = str(
            doc.get("decision", "")
        )
        if decision not in (
            "aceptar",
            "rechazar",
        ):
            self._api_error(
                400,
                "decision invalida",
            )
            return
        accepted = (
            decision == "aceptar"
        )
        result = (
            self.store.decide_proposal(
                proposal_id=str(
                    doc.get(
                        "proposal_id",
                        "",
                    )
                ),
                accepted=accepted,
            )
        )
        if accepted:
            result["network"] = (
                self._network_on_hire(
                    str(
                        result["job_id"]
                    ),
                    str(
                        result[
                            "worker_account"
                        ]
                    ),
                )
            )
        self._ok(result)

    def _api_hire(self) -> None:
        doc = self._read_json()
        if doc is None:
            self._api_error(
                400, "invalid JSON"
            )
            return
        job_id = str(
            doc.get("job_id", "")
        )
        worker_account = str(
            doc.get(
                "worker_account", ""
            )
        )
        hire = self.store.hire_worker(
            hire_id=_new_hire_id(),
            job_id=job_id,
            worker_account=(
                worker_account
            ),
        )
        network = (
            self._network_on_hire(
                job_id,
                worker_account,
            )
        )
        self._ok(
            {
                "hire": hire,
                "network": network,
            }
        )

    def _api_leave(self) -> None:
        doc = self._read_json()
        if doc is None:
            self._api_error(
                400, "invalid JSON"
            )
            return
        job_id = str(
            doc.get("job_id", "")
        )
        worker_account = str(
            doc.get(
                "worker_account", ""
            )
        )
        result = (
            self.store.worker_leaves(
                job_id=job_id,
                worker_account=(
                    worker_account
                ),
            )
        )
        self._network_on_leave(
            job_id, worker_account
        )
        self._ok(result)


def serve_mpe(
    store: MpeStore,
    client: object,
    *,
    host: str = "127.0.0.1",
    port: int = 0,
) -> ThreadingHTTPServer:
    handler = type(
        "BoundMpeHandler",
        (MpeApiHandler,),
        {
            "store": store,
            "link": MpeLink(client),
        },
    )
    server = ThreadingHTTPServer(
        (host, port), handler,
    )
    server.bound_port = (
        server.server_address[1]
    )
    return server
