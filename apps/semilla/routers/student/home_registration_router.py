
"""Home Registration Router (S-4) - API de
matricula desde casa sobre el server vivo.

RUTAS (el server real sirve todo bajo /semilla):
  POST /semilla/api/home-registration -> start
  GET  /semilla/api/home-registration/{id}
  POST /semilla/api/home-registration/{id}/confirm
  GET  /semilla/api/home-registrations
       ?institution_id=...

Logica PURA (dict in -> (codigo, dict) out);
los tests la ejercitan sin red.
patch_hr_routes() conecta estas rutas al
SemillaApiHandler con monkey-patch ADITIVO e
IDEMPOTENTE (regla 51): las rutas existentes
quedan intactas y el fallback 'unknown api
route' sigue siendo el ultimo recurso.
El router se cachea PEGADO AL STORE (un router
por server vivo; sin claves id() globales que
pueden colisionar entre tests).

Regla 78: el menor trae su ZID de NACIMIENTO si
existe (SEMILLA lo CONSUME, jamas crea otro);
sin documentos NO impide iniciar (zid NONE).
SE-3: 2 encargados de retiro + 1 de emergencia.
Errores honestos 400/404/405/409/503 (regla 66)
— incluido 409 SIN_CUPOS si la escuela no tiene
aulas/cupo configurados: jamas se inventa
capacidad."""
from __future__ import annotations
from typing import Tuple
from apps.semilla.domain.student.student_registry_engine import (
    StudentRegistryEngine)
from apps.semilla.domain.student.home_registration_engine import (
    HomeRegistrationEngine)
from apps.semilla.domain.classroom.classroom_engine import (
    ClassroomEngine)
from apps.semilla.domain.academic.enrollment_engine import (
    EnrollmentEngine)

_REQ = ("responsable_zid", "responsable_name",
        "relation", "child_name",
        "institution_id", "level", "grade")


class HomeRegistrationRouter:
    """API matricula desde casa (S-4)."""

    def __init__(self, db, clock):
        reg = StudentRegistryEngine(db, clock)
        cls = ClassroomEngine(db, clock)
        enr = EnrollmentEngine(
            db, clock, classroom_engine=cls)
        self._hr = HomeRegistrationEngine(
            db, clock, student_registry=reg,
            classroom_engine=cls,
            enrollment_engine=enr)

    @staticmethod
    def _err(code, msg) -> Tuple[int, dict]:
        return (int(code),
                {"ok": False,
                 "error": str(msg)})

    def start(self, doc) -> Tuple[int, dict]:
        if not isinstance(doc, dict):
            return self._err(
                400, "body JSON requerido")
        missing = [
            f for f in _REQ
            if not str(doc.get(f, "")).strip()]
        if missing:
            return self._err(
                400, "faltan campos: "
                + ", ".join(missing))
        try:
            r = self._hr.start_request(
                responsable_zid=str(
                    doc.get("responsable_zid", "")),
                responsable_name=str(
                    doc.get("responsable_name", "")),
                relation=str(doc.get("relation", "")),
                child_name=str(
                    doc.get("child_name", "")),
                birth_date=str(
                    doc.get("birth_date", "")),
                child_zid=str(
                    doc.get("child_zid", "")),
                child_zid_status=str(
                    doc.get("child_zid_status",
                            "NONE") or "NONE"),
                institution_id=str(
                    doc.get("institution_id", "")),
                level=str(doc.get("level", "")),
                grade=str(doc.get("grade", "")),
                turn=str(doc.get("turn", "MATUTINA")
                         or "MATUTINA"),
                authorized_pickup=list(
                    doc.get("authorized_pickup")
                    or []),
                emergency_contacts=list(
                    doc.get("emergency_contacts")
                    or []))
        except ValueError as e:
            return self._err(400, str(e))
        if r.get("status") == "SIN_CUPOS":
            return (409, {
                "ok": False,
                "error": "SIN_CUPOS",
                "note": str(r.get("note", "")),
                "request": r})
        return (201, {"ok": True, "request": r})

    def get(self, request_id) -> Tuple[int, dict]:
        r = self._hr.get_request(
            str(request_id or ""))
        if not r:
            return self._err(
                404, "solicitud no encontrada")
        return (200, {"ok": True, "request": r})

    def confirm(self, request_id, doc
                ) -> Tuple[int, dict]:
        d = doc if isinstance(doc, dict) else {}
        actor = str(
            d.get("director_actor", "")
            or d.get("actor", "") or "escuela")
        try:
            res = self._hr.confirm_by_school(
                str(request_id or ""),
                director_actor=actor)
        except KeyError:
            return self._err(
                404, "solicitud no encontrada")
        except ValueError as e:
            msg = str(e)
            code = (409 if "SIN_CUPOS" in msg
                    else 400)
            return self._err(code, msg)
        return (200, dict({"ok": True}, **res))

    def pending(self, institution_id
                ) -> Tuple[int, dict]:
        rows = self._hr.pending_requests(
            str(institution_id or ""))
        return (200, {"ok": True,
                      "pending": rows,
                      "count": len(rows)})

    def dispatch(self, *, method, segs,
                 query=None, doc=None
                 ) -> Tuple[int, dict]:
        """segs SIN prefijos semilla/api."""
        q = query or {}

        def q1(k):
            v = q.get(k)
            if isinstance(v, list):
                return str(v[0]) if v else ""
            return str(v or "")

        try:
            m = str(method or "GET").upper()
            if segs[:1] == ["home-registrations"]:
                if m != "GET":
                    return self._err(405,
                                     "solo GET")
                return self.pending(
                    q1("institution_id"))
            if segs[:1] == ["home-registration"]:
                rest = list(segs[1:])
                if not rest:
                    if m == "POST":
                        return self.start(doc)
                    return self._err(405,
                                     "solo POST")
                rid = str(rest[0])
                if (len(rest) >= 2
                        and rest[1] == "confirm"):
                    if m != "POST":
                        return self._err(
                            405, "solo POST")
                    return self.confirm(rid, doc)
                if m == "GET":
                    return self.get(rid)
                return self._err(405, "solo GET")
            return self._err(404,
                             "ruta desconocida")
        except Exception as e:
            return self._err(
                500, "error interno: " + str(e))


def patch_hr_routes():
    """Conecta las rutas S-4 al SemillaApiHandler
    del server vivo (regla 51: monkey-patch
    aditivo e idempotente)."""
    import json as _json
    from urllib.parse import urlparse, parse_qs
    from apps.semilla import server as _srv

    H = _srv.SemillaApiHandler
    if getattr(H, "_HR_V2", False):
        return

    def _segs(self):
        segs = [p for p in urlparse(
            self.path).path.split("/") if p]
        while segs and segs[0] in ("semilla",
                                   "api"):
            segs = segs[1:]
        return segs

    def _wants(self):
        s = _segs(self)
        return bool(s) and s[0] in (
            "home-registration",
            "home-registrations")

    def _router(self):
        st = getattr(self, "store", None)
        if st is None:
            return None
        r = getattr(st, "_hr_router_cache", None)
        if r is None:
            try:
                r = HomeRegistrationRouter(
                    st._db, st._clock)
            except Exception:
                return None
            try:
                st._hr_router_cache = r
            except Exception:
                pass
        return r

    def _compute(self, doc, method):
        u = urlparse(self.path)
        r = _router(self)
        if r is None:
            return (503, {
                "ok": False,
                "error": "matricula desde casa"
                         " no disponible"})
        return r.dispatch(
            method=str(method),
            segs=_segs(self),
            query=parse_qs(u.query), doc=doc)

    def _handle(self, doc, method):
        code, payload = _compute(self, doc,
                                 method)
        body = _json.dumps(
            payload, default=str).encode(
            "utf-8")
        self.send_response(int(code))
        self.send_header(
            "Content-Type",
            "application/json")
        self.send_header(
            "Content-Length",
            str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    _orig_get = H._api_get
    _orig_post = H._api_post

    def _api_get(self, s):
        if _wants(self):
            return _handle(self, None, "GET")
        return _orig_get(self, s)

    def _api_post(self, s):
        if _wants(self):
            try:
                doc = self._read_json()
            except Exception:
                doc = None
            return _handle(self, doc, "POST")
        return _orig_post(self, s)

    H._api_get = _api_get
    H._api_post = _api_post
    H._hr_segs = _segs
    H._hr_wants = _wants
    H._hr_compute = _compute
    H._HR_V2 = True
