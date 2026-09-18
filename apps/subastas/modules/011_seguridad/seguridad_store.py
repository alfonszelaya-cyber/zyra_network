"""ZYRA MARKET - Modulo Seguridad (completo).

Auditoria de acciones criticas, incidentes con seguimiento,
reglas de seguridad configurables. Patron join."""
from __future__ import annotations

import threading
import time
import traceback
import uuid


def _now() -> str:
    return time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())


def _nid(prefix: str) -> str:
    return prefix + uuid.uuid4().hex[:10]


class SeguridadStore:
    def __init__(self, db, clock) -> None:
        self._db = db
        self._clock = clock
        self._lock = threading.Lock()
        self._ensure_schema()

    def _ensure_schema(self) -> None:
        self._run(
            "CREATE TABLE IF NOT EXISTS sbs_audit ("
            " aud_id TEXT PRIMARY KEY,"
            " actor TEXT NOT NULL,"
            " action TEXT NOT NULL,"
            " target TEXT NOT NULL,"
            " detail TEXT,"
            " created_at TEXT NOT NULL)"
        )
        self._run(
            "CREATE TABLE IF NOT EXISTS sbs_incidents ("
            " inc_id TEXT PRIMARY KEY,"
            " reported_by TEXT NOT NULL,"
            " subject TEXT NOT NULL,"
            " category TEXT NOT NULL,"
            " detail TEXT NOT NULL,"
            " status TEXT NOT NULL,"
            " resolution TEXT,"
            " created_at TEXT NOT NULL,"
            " updated_at TEXT NOT NULL)"
        )
        self._run(
            "CREATE TABLE IF NOT EXISTS sbs_security_rules ("
            " rule_id TEXT PRIMARY KEY,"
            " name TEXT NOT NULL,"
            " limit_value REAL NOT NULL,"
            " enabled INTEGER NOT NULL DEFAULT 1,"
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
            assembled += SeguridadStore._literal(v)
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

    def audit(self, *, actor, action, target, detail=None):
        actor = self._req(actor, "actor")
        action = self._req(action, "action")
        target = self._req(target, "target")
        with self._lock:
            aud_id = _nid("AUD-")
            self._run(
                "INSERT INTO sbs_audit (aud_id, actor, action, target,"
                " detail, created_at) VALUES (?, ?, ?, ?, ?, ?)",
                (aud_id, actor, action, target,
                 str(detail) if detail else None, _now()),
            )
            return {"aud_id": aud_id, "actor": actor,
                    "action": action, "target": target}

    def list_audit(self, limit=50):
        out = []
        for row in self._rows(
            "SELECT aud_id, actor, action, target, detail, created_at"
            " FROM sbs_audit ORDER BY created_at DESC LIMIT "
            + str(int(limit))
        ):
            out.append({
                "aud_id": self._field(row, "a", 0),
                "actor": self._field(row, "b", 1),
                "action": self._field(row, "c", 2),
                "target": self._field(row, "d", 3),
                "detail": self._field(row, "e", 4),
                "created_at": self._field(row, "f", 5),
            })
        return out

    def open_incident(self, *, reported_by, subject, category, detail):
        reported_by = self._req(reported_by, "reported_by")
        subject = self._req(subject, "subject")
        category = str(category or "").strip()
        if category not in ("cuenta", "transaccion", "contenido", "otro"):
            raise ValueError("categoria: cuenta/transaccion/contenido/otro")
        detail = self._req(detail, "detail")
        with self._lock:
            inc_id = _nid("INC-")
            now = _now()
            self._run(
                "INSERT INTO sbs_incidents (inc_id, reported_by,"
                " subject, category, detail, status, resolution,"
                " created_at, updated_at)"
                " VALUES (?, ?, ?, ?, ?, 'open', NULL, ?, ?)",
                (inc_id, reported_by, subject, category, detail, now, now),
            )
            return self.get_incident(inc_id)

    def _inc_row(self, inc_id):
        rows = self._rows(
            "SELECT inc_id, reported_by, subject, category, detail,"
            " status, resolution, created_at, updated_at"
            " FROM sbs_incidents WHERE inc_id = "
            + self._literal(inc_id)
        )
        if not rows:
            return None
        return rows[0]

    def get_incident(self, inc_id):
        row = self._inc_row(self._req(inc_id, "inc_id"))
        if row is None:
            return None
        return {
            "inc_id": self._field(row, "a", 0),
            "reported_by": self._field(row, "b", 1),
            "subject": self._field(row, "c", 2),
            "category": self._field(row, "d", 3),
            "detail": self._field(row, "e", 4),
            "status": self._field(row, "f", 5),
            "resolution": self._field(row, "g", 6),
        }

    def close_incident(self, inc_id, *, actor, resolution):
        inc_id = self._req(inc_id, "inc_id")
        self._req(actor, "actor")
        resolution = self._req(resolution, "resolution")
        with self._lock:
            self._run(
                "UPDATE sbs_incidents SET status = 'closed',"
                " resolution = " + self._literal(resolution)
                + ", updated_at = " + self._literal(_now())
                + " WHERE inc_id = " + self._literal(inc_id)
            )
        return self.get_incident(inc_id)

    def list_incidents(self, status=None):
        sql = (
            "SELECT inc_id, reported_by, subject, category, detail,"
            " status, resolution, created_at, updated_at"
            " FROM sbs_incidents"
        )
        if status:
            sql += " WHERE status = " + self._literal(str(status))
        sql += " ORDER BY created_at DESC"
        out = []
        for row in self._rows(sql):
            out.append({
                "inc_id": self._field(row, "a", 0),
                "reported_by": self._field(row, "b", 1),
                "subject": self._field(row, "c", 2),
                "category": self._field(row, "d", 3),
                "status": self._field(row, "f", 5),
            })
        return out

    def set_rule(self, *, name, limit_value, enabled=True):
        name = self._req(name, "name")
        limit_value = float(limit_value)
        with self._lock:
            row = self._rows(
                "SELECT rule_id FROM sbs_security_rules WHERE name = "
                + self._literal(name)
            )
            if row:
                rid = str(self._field(row[0], "a", 0))
                self._run(
                    "UPDATE sbs_security_rules SET limit_value = "
                    + repr(limit_value)
                    + ", enabled = "
                    + ("1" if enabled else "0")
                    + " WHERE rule_id = " + self._literal(rid)
                )
            else:
                rid = _nid("RUL-")
                self._run(
                    "INSERT INTO sbs_security_rules (rule_id, name,"
                    " limit_value, enabled, created_at)"
                    " VALUES (?, ?, ?, ?, ?)",
                    (rid, name, limit_value,
                     1 if enabled else 0, _now()),
                )
            return {"rule_id": rid, "name": name,
                    "limit_value": limit_value, "enabled": enabled}

    def list_rules(self):
        out = []
        for row in self._rows(
            "SELECT rule_id, name, limit_value, enabled, created_at"
            " FROM sbs_security_rules ORDER BY created_at ASC"
        ):
            out.append({
                "rule_id": self._field(row, "a", 0),
                "name": self._field(row, "b", 1),
                "limit_value": self._field(row, "c", 2),
                "enabled": bool(self._field(row, "d", 3)),
            })
        return out


def market_gov_seguridad_page(self) -> str:
    user = self._sess_user()
    if user is None or user.get("role") not in ("gobierno", "admin"):
        body = "<p>Solo gobierno/admin.</p>"
        return self._page_wrap("ZYRA MARKET - Gov Seguridad", body)
    audit = self.seg.list_audit(20)
    incs = self.seg.list_incidents()
    rules = self.seg.list_rules()
    a_rows = []
    for a in audit:
        a_rows.append(
            "<p>- [%s] %s -> %s (%s)</p>" % (
                a["created_at"], a["actor"], a["action"], a["target"]))
    if not a_rows:
        a_rows.append("<p>Sin auditoria.</p>")
    i_rows = []
    for i in incs:
        i_rows.append(
            "<p>- <b>%s</b> (%s) sobre %s <code>%s</code></p>" % (
                i["category"], i["status"], i["subject"], i["inc_id"]))
    if not i_rows:
        i_rows.append("<p>Sin incidentes.</p>")
    r_rows = []
    for r in rules:
        on = "ON" if r["enabled"] else "OFF"
        r_rows.append(
            "<p>- %s: limite %s [%s]</p>" % (
                r["name"], str(r["limit_value"]), on))
    if not r_rows:
        r_rows.append("<p>Sin reglas configuradas.</p>")
    body = "".join([
        "<div class='card'><h2>Auditoria (ultimas 20)</h2>",
        "".join(a_rows),
        "</div>",
        "<div class='card'><h2>Incidentes de seguridad</h2>",
        "<input id='iSub' placeholder='Cuenta/cosa afectada'>",
        "<select id='iCat'>",
        "<option value='cuenta'>cuenta</option>",
        "<option value='transaccion'>transaccion</option>",
        "<option value='contenido'>contenido</option>",
        "<option value='otro'>otro</option>",
        "</select>",
        "<input id='iDet' placeholder='Detalle'>",
        "<button id='btnInc'>Abrir incidente</button>",
        "".join(i_rows),
        "</div>",
        "<div class='card'><h2>Reglas de seguridad</h2>",
        "<input id='rName' placeholder='Nombre de regla'>",
        "<input id='rVal' type='number' step='0.01' placeholder='Limite'>",
        "<button id='btnRule'>Guardar regla</button>",
        "".join(r_rows),
        "</div>",
        "<p id='msg'></p>",
        "<script>",
        "function v(id){return document.getElementById(id).value;}",
        "function num(id){var x=parseFloat(v(id));return isNaN(x)?0:x;}",
        "function post(path,payload){",
        "fetch(path,{method:'POST',",
        "headers:{'Content-Type':'application/json'},",
        "body:JSON.stringify(payload)})",
        ".then(function(r){return r.json();})",
        ".then(function(d){if(d.ok){location.reload();}",
        "else{document.getElementById('msg').textContent='Error: '+(d.error||'');}})",
        ".catch(function(e){document.getElementById('msg').textContent='Error: '+e;});}",
        "document.getElementById('btnInc').addEventListener('click',function(){",
        "post('/subastas/api/gov-seguridad',{action:'open_incident',",
        "subject:v('iSub'),category:v('iCat'),detail:v('iDet')});});",
        "document.getElementById('btnRule').addEventListener('click',function(){",
        "post('/subastas/api/gov-seguridad',{action:'set_rule',",
        "name:v('rName'),limit_value:num('rVal')});});",
        "</script>",
    ])
    return self._page_wrap("ZYRA MARKET - Gov Seguridad", body)


def market_gov_seguridad_api(self) -> None:
    try:
        user = self._sess_user()
        if user is None or user.get("role") not in ("gobierno", "admin"):
            self._send_json(403, {"ok": False, "error": "solo gobierno/admin"})
            return
        doc = self._read_json()
        if doc is None:
            self._send_json(400, {"ok": False, "error": "invalid JSON"})
            return
        action = str(doc.get("action", ""))
        if action == "open_incident":
            inc = self.seg.open_incident(
                reported_by=user["username"],
                subject=str(doc.get("subject", "")),
                category=str(doc.get("category", "otro")),
                detail=str(doc.get("detail", "")))
            self._send_json(201, {"ok": True, "data": inc})
            return
        if action == "close_incident":
            inc = self.seg.close_incident(
                str(doc.get("inc_id", "")),
                actor=user["username"],
                resolution=str(doc.get("resolution", "")))
            self._send_json(200, {"ok": True, "data": inc})
            return
        if action == "set_rule":
            r = self.seg.set_rule(
                name=str(doc.get("name", "")),
                limit_value=doc.get("limit_value", 0),
                enabled=bool(doc.get("enabled", True)))
            self._send_json(200, {"ok": True, "data": r})
            return
        self._send_json(
            400, {"ok": False, "error": "accion desconocida"}
        )
    except Exception:
        self._send_json(500, {
            "ok": False,
            "error": "server error",
            "trace": traceback.format_exc(),
        })
