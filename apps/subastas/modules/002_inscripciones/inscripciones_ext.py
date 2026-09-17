"""ZYRA MARKET - Modulo 002 Inscripciones (extension).

Entidades (empresa/inversionista/organizacion) con
verificacion de gobierno, verificacion de documentos
sellada en la Red, metodos de pago multiples por
usuario, e historial completo de inscripcion."""
from __future__ import annotations

import threading
import time
import uuid


def _now() -> str:
    return time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())


def _nid(prefix: str) -> str:
    return prefix + uuid.uuid4().hex[:10]


ENTITY_TYPES = ("empresa", "inversionista", "organizacion")
PM_KINDS = ("cartera", "tarjeta", "banco", "cripto")


class InscripcionesExt:
    def __init__(self, db, clock, net_client) -> None:
        self._db = db
        self._clock = clock
        self._net = net_client
        self._lock = threading.Lock()
        self._ensure_schema()

    def _ensure_schema(self) -> None:
        self._run(
            "CREATE TABLE IF NOT EXISTS sbs_entities ("
            " entity_id TEXT PRIMARY KEY,"
            " user_id TEXT NOT NULL,"
            " etype TEXT NOT NULL,"
            " name TEXT NOT NULL,"
            " rep_name TEXT NOT NULL,"
            " rep_doc TEXT NOT NULL,"
            " status TEXT NOT NULL,"
            " created_at TEXT NOT NULL,"
            " updated_at TEXT NOT NULL)"
        )
        self._run(
            "CREATE TABLE IF NOT EXISTS sbs_doc_verifications ("
            " dvid TEXT PRIMARY KEY,"
            " user_id TEXT NOT NULL,"
            " doc_ref TEXT NOT NULL,"
            " network_doc_id TEXT,"
            " status TEXT NOT NULL,"
            " created_at TEXT NOT NULL,"
            " verified_at TEXT)"
        )
        self._run(
            "CREATE TABLE IF NOT EXISTS sbs_payment_methods ("
            " pm_id TEXT PRIMARY KEY,"
            " user_id TEXT NOT NULL,"
            " kind TEXT NOT NULL,"
            " label TEXT NOT NULL,"
            " detail TEXT,"
            " is_default INTEGER NOT NULL DEFAULT 0,"
            " created_at TEXT NOT NULL)"
        )
        self._run(
            "CREATE TABLE IF NOT EXISTS sbs_inscription_history ("
            " hid TEXT PRIMARY KEY,"
            " user_id TEXT NOT NULL,"
            " kind TEXT NOT NULL,"
            " detail TEXT NOT NULL,"
            " created_at TEXT NOT NULL)"
        )

    def _run(self, sql, params=()):
        if not params:
            self._db.execute(sql)
            return
        try:
            self._db.execute(sql, params)
            return
        except TypeError:
            self._db.execute(self._inline(sql, params))

    @staticmethod
    def _inline(sql, params):
        parts = sql.split("?")
        if len(parts) != len(params) + 1:
            return sql
        assembled = parts[0]
        for i, v in enumerate(params):
            assembled += InscripcionesExt._literal(v)
            assembled += parts[i + 1]
        return assembled

    @staticmethod
    def _literal(value):
        if value is None:
            return "NULL"
        if isinstance(value, bool):
            return "1" if value else "0"
        if isinstance(value, (int, float)):
            return repr(value)
        return "'" + str(value).replace("'", "''") + "'"

    def _rows(self, sql):
        for name in ("query", "fetchall", "fetch_all", "fetch", "select"):
            fn = getattr(self._db, name, None)
            if callable(fn):
                try:
                    rows = fn(sql)
                    if rows is not None:
                        return list(rows)
                except Exception:
                    continue
        try:
            cur = self._db.execute(sql)
        except Exception:
            return []
        if cur is None:
            return []
        try:
            return list(cur.fetchall())
        except Exception:
            return []

    @staticmethod
    def _field(row, key, index):
        if isinstance(row, dict):
            return row.get(key)
        try:
            return row[index]
        except Exception:
            return None

    @staticmethod
    def _req(value, name):
        text = str(value or "").strip()
        if not text:
            raise ValueError("%s es obligatorio" % name)
        return text

    def _hist(self, user_id, kind, detail):
        self._run(
            "INSERT INTO sbs_inscription_history (hid, user_id,"
            " kind, detail, created_at) VALUES (?, ?, ?, ?, ?)",
            (_nid("HIS-"), user_id, kind, detail, _now()),
        )

    def register_entity(self, *, user_id, etype, name, rep_name, rep_doc):
        user_id = self._req(user_id, "user_id")
        etype = str(etype or "").strip()
        if etype not in ENTITY_TYPES:
            raise ValueError("tipo debe ser: %s" % ", ".join(ENTITY_TYPES))
        name = self._req(name, "name")
        rep_name = self._req(rep_name, "rep_name")
        rep_doc = self._req(rep_doc, "rep_doc")
        with self._lock:
            entity_id = _nid("ENT-")
            now = _now()
            self._run(
                "INSERT INTO sbs_entities (entity_id, user_id, etype,"
                " name, rep_name, rep_doc, status, created_at, updated_at)"
                " VALUES (?, ?, ?, ?, ?, ?, 'pending', ?, ?)",
                (entity_id, user_id, etype, name, rep_name, rep_doc, now, now),
            )
            self._hist(user_id, "entidad", "%s registrada: %s (%s)" % (etype, name, entity_id))
            return self.get_entity(entity_id)

    def get_entity(self, entity_id):
        entity_id = self._req(entity_id, "entity_id")
        rows = self._rows(
            "SELECT entity_id, user_id, etype, name, rep_name,"
            " rep_doc, status, created_at, updated_at"
            " FROM sbs_entities WHERE entity_id = "
            + self._literal(entity_id)
        )
        if not rows:
            return None
        row = rows[0]
        return {
            "entity_id": self._field(row, "a", 0),
            "user_id": self._field(row, "b", 1),
            "etype": self._field(row, "c", 2),
            "name": self._field(row, "d", 3),
            "rep_name": self._field(row, "e", 4),
            "rep_doc": self._field(row, "f", 5),
            "status": self._field(row, "g", 6),
        }

    def list_entities(self, status=None):
        sql = (
            "SELECT entity_id, user_id, etype, name, rep_name,"
            " rep_doc, status, created_at, updated_at FROM sbs_entities"
        )
        if status:
            sql += " WHERE status = " + self._literal(str(status))
        sql += " ORDER BY created_at DESC"
        out = []
        for row in self._rows(sql):
            out.append({
                "entity_id": self._field(row, "a", 0),
                "user_id": self._field(row, "b", 1),
                "etype": self._field(row, "c", 2),
                "name": self._field(row, "d", 3),
                "rep_name": self._field(row, "e", 4),
                "status": self._field(row, "g", 6),
            })
        return out

    def verify_entity(self, entity_id, *, approve):
        entity_id = self._req(entity_id, "entity_id")
        with self._lock:
            row = self._rows(
                "SELECT user_id, name FROM sbs_entities WHERE entity_id = "
                + self._literal(entity_id)
            )
            if not row:
                raise LookupError("entidad no encontrada")
            user_id = str(self._field(row[0], "u", 0))
            name = str(self._field(row[0], "n", 1))
            status = "verified" if approve else "rejected"
            self._run(
                "UPDATE sbs_entities SET status = "
                + self._literal(status)
                + ", updated_at = " + self._literal(_now())
                + " WHERE entity_id = " + self._literal(entity_id)
            )
            self._hist(user_id, "verificacion", "entidad %s: %s" % (name, status))
        return self.get_entity(entity_id)

    def submit_document(self, *, user_id, doc_ref):
        user_id = self._req(user_id, "user_id")
        doc_ref = self._req(doc_ref, "doc_ref")
        ok = False
        data = None
        try:
            ok, data, err = self._net.post(
                "/documents/seal",
                {"title": "doc-inscripcion:%s" % doc_ref, "sha256": doc_ref},
            )
        except Exception:
            pass
        network_doc_id = None
        if ok and data:
            if isinstance(data, dict):
                for k, v in data.items():
                    if "doc" in str(k).lower() and isinstance(v, str):
                        network_doc_id = v
                        break
        with self._lock:
            dvid = _nid("DVC-")
            status = "sealed" if (ok and network_doc_id) else "pending_network"
            self._run(
                "INSERT INTO sbs_doc_verifications (dvid, user_id,"
                " doc_ref, network_doc_id, status, created_at, verified_at)"
                " VALUES (?, ?, ?, ?, ?, ?, NULL)",
                (dvid, user_id, doc_ref, network_doc_id, status, _now()),
            )
            self._hist(user_id, "documento", "documento %s: %s" % (doc_ref, status))
            return self.get_document(dvid)

    def get_document(self, dvid):
        dvid = self._req(dvid, "dvid")
        rows = self._rows(
            "SELECT dvid, user_id, doc_ref, network_doc_id, status,"
            " created_at, verified_at FROM sbs_doc_verifications"
            " WHERE dvid = " + self._literal(dvid)
        )
        if not rows:
            return None
        row = rows[0]
        return {
            "dvid": self._field(row, "a", 0),
            "user_id": self._field(row, "b", 1),
            "doc_ref": self._field(row, "c", 2),
            "network_doc_id": self._field(row, "d", 3),
            "status": self._field(row, "e", 4),
            "created_at": self._field(row, "f", 5),
            "verified_at": self._field(row, "g", 6),
        }

    def list_documents(self, status=None):
        sql = (
            "SELECT dvid, user_id, doc_ref, network_doc_id, status,"
            " created_at, verified_at FROM sbs_doc_verifications"
        )
        if status:
            sql += " WHERE status = " + self._literal(str(status))
        sql += " ORDER BY created_at DESC"
        out = []
        for row in self._rows(sql):
            out.append({
                "dvid": self._field(row, "a", 0),
                "user_id": self._field(row, "b", 1),
                "doc_ref": self._field(row, "c", 2),
                "status": self._field(row, "e", 4),
            })
        return out

    def verify_document(self, dvid, *, approve):
        dvid = self._req(dvid, "dvid")
        with self._lock:
            row = self._rows(
                "SELECT user_id, doc_ref FROM sbs_doc_verifications"
                " WHERE dvid = " + self._literal(dvid)
            )
            if not row:
                raise LookupError("documento no encontrado")
            user_id = str(self._field(row[0], "u", 0))
            doc_ref = str(self._field(row[0], "d", 1))
            status = "verified" if approve else "rejected"
            self._run(
                "UPDATE sbs_doc_verifications SET status = "
                + self._literal(status)
                + ", verified_at = " + self._literal(_now())
                + " WHERE dvid = " + self._literal(dvid)
            )
            self._hist(user_id, "verificacion", "documento %s: %s" % (doc_ref, status))
        return self.get_document(dvid)

    def add_payment_method(self, *, user_id, kind, label, detail=None, make_default=False):
        user_id = self._req(user_id, "user_id")
        kind = str(kind or "").strip()
        if kind not in PM_KINDS:
            raise ValueError("tipo debe ser: %s" % ", ".join(PM_KINDS))
        label = self._req(label, "label")
        with self._lock:
            pm_id = _nid("PMT-")
            if make_default:
                self._run(
                    "UPDATE sbs_payment_methods SET is_default = 0"
                    " WHERE user_id = " + self._literal(user_id)
                )
            self._run(
                "INSERT INTO sbs_payment_methods (pm_id, user_id,"
                " kind, label, detail, is_default, created_at)"
                " VALUES (?, ?, ?, ?, ?, ?, ?)",
                (
                    pm_id, user_id, kind, label,
                    str(detail) if detail else None,
                    1 if make_default else 0,
                    _now(),
                ),
            )
            self._hist(user_id, "metodo_pago", "%s: %s agregado" % (kind, label))
            return self.get_payment_method(pm_id)

    def get_payment_method(self, pm_id):
        pm_id = self._req(pm_id, "pm_id")
        rows = self._rows(
            "SELECT pm_id, user_id, kind, label, detail, is_default,"
            " created_at FROM sbs_payment_methods WHERE pm_id = "
            + self._literal(pm_id)
        )
        if not rows:
            return None
        row = rows[0]
        return {
            "pm_id": self._field(row, "a", 0),
            "user_id": self._field(row, "b", 1),
            "kind": self._field(row, "c", 2),
            "label": self._field(row, "d", 3),
            "detail": self._field(row, "e", 4),
            "is_default": bool(self._field(row, "f", 5)),
        }

    def list_payment_methods(self, user_id):
        user_id = self._req(user_id, "user_id")
        out = []
        for row in self._rows(
            "SELECT pm_id, user_id, kind, label, detail, is_default,"
            " created_at FROM sbs_payment_methods WHERE user_id = "
            + self._literal(user_id)
            + " ORDER BY is_default DESC, created_at ASC"
        ):
            out.append({
                "pm_id": self._field(row, "a", 0),
                "kind": self._field(row, "c", 2),
                "label": self._field(row, "d", 3),
                "is_default": bool(self._field(row, "f", 5)),
            })
        return out

    def history(self, user_id):
        user_id = self._req(user_id, "user_id")
        out = []
        for row in self._rows(
            "SELECT hid, kind, detail, created_at"
            " FROM sbs_inscription_history WHERE user_id = "
            + self._literal(user_id)
            + " ORDER BY created_at ASC"
        ):
            out.append({
                "hid": self._field(row, "a", 0),
                "kind": self._field(row, "b", 1),
                "detail": self._field(row, "c", 2),
                "created_at": self._field(row, "d", 3),
            })
        return out


def market_ins_ext_page(self) -> str:
    user = self._sess_user()
    self._require_role(user, "comprador", "vendedor", "gobierno", "admin")
    uid = user["user_id"]
    entities = self.iext.list_entities()
    docs = self.iext.list_documents()
    pms = self.iext.list_payment_methods(uid)
    hist = self.iext.history(uid)
    e_rows = []
    for e in entities:
        e_rows.append(
            "<p>- <b>%s</b> (%s) %s: %s</p>" % (
                e["name"], e["etype"], e["status"], e["entity_id"]))
    d_rows = []
    for d in docs:
        d_rows.append(
            "<p>- <b>%s</b>: %s</p>" % (d["doc_ref"], d["status"]))
    p_rows = []
    for p in pms:
        star = " (predeterminado)" if p["is_default"] else ""
        p_rows.append(
            "<p>- <b>%s</b> %s%s</p>" % (p["label"], p["kind"], star))
    h_rows = []
    for h in hist:
        h_rows.append(
            "<p>[%s] %s: %s</p>" % (
                h["created_at"], h["kind"], h["detail"]))
    if not e_rows:
        e_rows.append("<p>Sin entidades.</p>")
    if not d_rows:
        d_rows.append("<p>Sin documentos.</p>")
    if not p_rows:
        p_rows.append("<p>Sin metodos de pago.</p>")
    if not h_rows:
        h_rows.append("<p>Sin historial.</p>")
    body = "".join([
        "<div class='card'><h2>Registrar entidad</h2>",
        "<p>Empresa, inversionista u organizacion (el gobierno verifica).</p>",
        "<select id='enType'>",
        "<option value='empresa'>empresa</option>",
        "<option value='inversionista'>inversionista</option>",
        "<option value='organizacion'>organizacion</option>",
        "</select>",
        "<input id='enName' placeholder='Nombre'>",
        "<input id='enRep' placeholder='Representante'>",
        "<input id='enDoc' placeholder='Documento del representante'>",
        "<button id='btnEnt'>Registrar entidad</button>",
        "".join(e_rows),
        "</div>",
        "<div class='card'><h2>Verificar mi documento (sellado en la Red)</h2>",
        "<input id='dvRef' placeholder='Referencia del documento'>",
        "<button id='btnDoc'>Enviar a sellar</button>",
        "".join(d_rows),
        "</div>",
        "<div class='card'><h2>Mis metodos de pago</h2>",
        "<select id='pmKind'>",
        "<option value='cartera'>cartera</option>",
        "<option value='tarjeta'>tarjeta</option>",
        "<option value='banco'>banco</option>",
        "<option value='cripto'>cripto</option>",
        "</select>",
        "<input id='pmLabel' placeholder='Etiqueta (ej. mi banco)'>",
        "<input id='pmDetail' placeholder='Detalle'>",
        "<button id='btnPm'>Agregar metodo</button>",
        "".join(p_rows),
        "</div>",
        "<div class='card'><h2>Historial de mi inscripcion</h2>",
        "".join(h_rows),
        "</div>",
        "<p id='msg'></p>",
        "<script>",
        "function v(id){return document.getElementById(id).value;}",
        "function post(path,payload){",
        "fetch(path,{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify(payload)})",
        ".then(function(r){return r.json();})",
        ".then(function(d){if(d.ok){location.reload();}",
        "else{document.getElementById('msg').textContent='Error: '+(d.error||'');}})",
        ".catch(function(e){document.getElementById('msg').textContent='Error: '+e;});}",
        "document.getElementById('btnEnt').addEventListener('click',function(){",
        "post('/subastas/api/inscripcion/entidad',{etype:v('enType'),name:v('enName'),rep_name:v('enRep'),rep_doc:v('enDoc')});});",
        "document.getElementById('btnDoc').addEventListener('click',function(){",
        "post('/subastas/api/inscripcion/documento',{doc_ref:v('dvRef')});});",
        "document.getElementById('btnPm').addEventListener('click',function(){",
        "post('/subastas/api/inscripcion/pago',{kind:v('pmKind'),label:v('pmLabel'),detail:v('pmDetail')});});",
        "</script>",
    ])
    return self._page_wrap("ZYRA MARKET - Mi Inscripcion", body)


def market_gov_inscripcion_page(self) -> str:
    user = self._sess_user()
    self._require_role(user, "gobierno", "admin")
    entities = self.iext.list_entities()
    docs = self.iext.list_documents()
    e_rows = []
    for e in entities:
        e_rows.append(
            "<p>- <b>%s</b> (%s) %s: <code>%s</code></p>" % (
                e["name"], e["etype"], e["status"], e["entity_id"]))
    d_rows = []
    for d in docs:
        d_rows.append(
            "<p>- <b>%s</b>: %s <code>%s</code></p>" % (
                d["doc_ref"], d["status"], d["dvid"]))
    if not e_rows:
        e_rows.append("<p>Sin entidades pendientes.</p>")
    if not d_rows:
        d_rows.append("<p>Sin documentos pendientes.</p>")
    body = "".join([
        "<div class='card'><h2>Verificar entidad</h2>",
        "<input id='eId' placeholder='ID de entidad (ENT-...)'>",
        "<select id='eOk'>",
        "<option value='true'>Verificar</option>",
        "<option value='false'>Rechazar</option>",
        "</select>",
        "<button id='btnEv'>Aplicar</button>",
        "".join(e_rows),
        "</div>",
        "<div class='card'><h2>Verificar documento</h2>",
        "<input id='dId' placeholder='ID de documento (DVC-...)'>",
        "<select id='dOk'>",
        "<option value='true'>Verificar</option>",
        "<option value='false'>Rechazar</option>",
        "</select>",
        "<button id='btnDv'>Aplicar</button>",
        "".join(d_rows),
        "</div>",
        "<p id='msg'></p>",
        "<script>",
        "function v(id){return document.getElementById(id).value;}",
        "function post(path,payload){",
        "fetch(path,{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify(payload)})",
        ".then(function(r){return r.json();})",
        ".then(function(d){if(d.ok){location.reload();}",
        "else{document.getElementById('msg').textContent='Error: '+(d.error||'');}})",
        ".catch(function(e){document.getElementById('msg').textContent='Error: '+e;});}",
        "document.getElementById('btnEv').addEventListener('click',function(){",
        "post('/subastas/api/inscripcion/verificar-entidad',{entity_id:v('eId'),approve:v('eOk')==='true'});});",
        "document.getElementById('btnDv').addEventListener('click',function(){",
        "post('/subastas/api/inscripcion/verificar-documento',{dvid:v('dId'),approve:v('dOk')==='true'});});",
        "</script>",
    ])
    return self._page_wrap("ZYRA MARKET - Gobierno Inscripciones", body)


def market_entity_register(self) -> None:
    user = self._sess_user()
    self._require_role(user, "comprador", "vendedor", "gobierno", "admin")
    doc = self._read_json()
    if doc is None:
        self._send_json(400, {"ok": False, "error": "invalid JSON"})
        return
    entity = self.iext.register_entity(
        user_id=user["user_id"],
        etype=str(doc.get("etype", "")),
        name=str(doc.get("name", "")),
        rep_name=str(doc.get("rep_name", "")),
        rep_doc=str(doc.get("rep_doc", "")),
    )
    self._send_json(201, {"ok": True, "data": entity})


def market_doc_submit(self) -> None:
    user = self._sess_user()
    self._require_role(user, "comprador", "vendedor", "gobierno", "admin")
    doc = self._read_json()
    if doc is None:
        self._send_json(400, {"ok": False, "error": "invalid JSON"})
        return
    docv = self.iext.submit_document(
        user_id=user["user_id"],
        doc_ref=str(doc.get("doc_ref", "")),
    )
    self._send_json(201, {"ok": True, "data": docv})


def market_pm_add(self) -> None:
    user = self._sess_user()
    self._require_role(user, "comprador", "vendedor", "gobierno", "admin")
    doc = self._read_json()
    if doc is None:
        self._send_json(400, {"ok": False, "error": "invalid JSON"})
        return
    pm = self.iext.add_payment_method(
        user_id=user["user_id"],
        kind=str(doc.get("kind", "")),
        label=str(doc.get("label", "")),
        detail=doc.get("detail"),
        make_default=bool(doc.get("make_default", False)),
    )
    self._send_json(201, {"ok": True, "data": pm})


def market_verify_entity(self) -> None:
    user = self._sess_user()
    self._require_role(user, "gobierno", "admin")
    doc = self._read_json()
    if doc is None:
        self._send_json(400, {"ok": False, "error": "invalid JSON"})
        return
    entity = self.iext.verify_entity(
        str(doc.get("entity_id", "")),
        approve=bool(doc.get("approve", False)),
    )
    self._send_json(200, {"ok": True, "data": entity})


def market_verify_document(self) -> None:
    user = self._sess_user()
    self._require_role(user, "gobierno", "admin")
    doc = self._read_json()
    if doc is None:
        self._send_json(400, {"ok": False, "error": "invalid JSON"})
        return
    docv = self.iext.verify_document(
        str(doc.get("dvid", "")),
        approve=bool(doc.get("approve", False)),
    )
    self._send_json(200, {"ok": True, "data": docv})
