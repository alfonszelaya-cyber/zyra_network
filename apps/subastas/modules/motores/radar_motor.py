"""RADAR TRANSVERSAL - motor unico con instancias."""
from __future__ import annotations

import threading
import time
import traceback
import uuid


def _now() -> str:
    return time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())


def _nid(prefix: str) -> str:
    return prefix + uuid.uuid4().hex[:10]


class RadarMotor:
    def __init__(self, db, clock, net_client) -> None:
        self._db = db
        self._clock = clock
        self._net = net_client
        self._lock = threading.RLock()
        self._ensure_schema()

    def _ensure_schema(self) -> None:
        self._run(
            "CREATE TABLE IF NOT EXISTS sbs_radar_scans ("
            " scan_id TEXT PRIMARY KEY,"
            " instance TEXT NOT NULL,"
            " operator TEXT NOT NULL,"
            " summary TEXT NOT NULL,"
            " findings INTEGER NOT NULL DEFAULT 0,"
            " created_at TEXT NOT NULL)"
        )
        self._run(
            "CREATE TABLE IF NOT EXISTS sbs_radar_findings ("
            " fin_id TEXT PRIMARY KEY,"
            " scan_id TEXT NOT NULL,"
            " label TEXT NOT NULL,"
            " score REAL NOT NULL,"
            " detail TEXT,"
            " tokenized INTEGER NOT NULL DEFAULT 0,"
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
            assembled += RadarMotor._literal(v)
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

    def scan(self, *, instance, operator, findings, summary):
        instance = self._req(instance, "instance")
        operator = self._req(operator, "operator")
        summary = self._req(summary, "summary")
        if instance not in ("market", "axis", "general"):
            raise ValueError("instancia: market/axis/general")
        with self._lock:
            scan_id = _nid("SCN-")
            n = len(findings or [])
            self._run(
                "INSERT INTO sbs_radar_scans (scan_id, instance,"
                " operator, summary, findings, created_at)"
                " VALUES (?, ?, ?, ?, ?, ?)",
                (scan_id, instance, operator, summary, n, _now()),
            )
            saved = []
            for f in (findings or []):
                fin_id = _nid("FND-")
                self._run(
                    "INSERT INTO sbs_radar_findings (fin_id,"
                    " scan_id, label, score, detail, tokenized,"
                    " created_at)"
                    " VALUES (?, ?, ?, ?, ?, 0, ?)",
                    (fin_id, scan_id,
                     str(f.get("label", "hallazgo")),
                     float(f.get("score", 0)),
                     str(f.get("detail", "")) if f.get("detail") else None,
                     _now()),
                )
                saved.append({"fin_id": fin_id,
                              "label": f.get("label", "hallazgo"),
                              "score": float(f.get("score", 0))})
            return {"scan_id": scan_id, "findings": saved,
                    "count": len(saved)}

    def tokenize_finding(self, fin_id, *, operator):
        fin_id = self._req(fin_id, "fin_id")
        self._req(operator, "operator")
        with self._lock:
            rows = self._rows(
                "SELECT label, score, tokenized FROM sbs_radar_findings"
                " WHERE fin_id = " + self._literal(fin_id)
            )
            if not rows:
                raise LookupError("hallazgo no encontrado")
            if int(self._field(rows[0], "c", 2) or 0) == 1:
                raise ValueError("hallazgo ya tokenizado")
            label = str(self._field(rows[0], "a", 0))
            score = float(self._field(rows[0], "b", 1) or 0)
            ok = False
            try:
                ok, data, err = self._net.post(
                    "/tokens/earn",
                    {
                        "subject_zid": operator,
                        "activity": "radar_finding",
                        "ref_type": "radar",
                        "ref_id": fin_id,
                    },
                )
            except Exception:
                pass
            tokenized = 1 if ok else 0
            self._run(
                "UPDATE sbs_radar_findings SET tokenized = "
                + str(tokenized)
                + " WHERE fin_id = " + self._literal(fin_id)
            )
            return {
                "fin_id": fin_id,
                "label": label,
                "score": score,
                "tokenized": bool(ok),
                "network_ok": ok,
            }

    def list_scans(self, instance=None):
        sql = (
            "SELECT scan_id, instance, operator, summary,"
            " findings, created_at FROM sbs_radar_scans"
        )
        if instance:
            sql += " WHERE instance = " + self._literal(str(instance))
        sql += " ORDER BY created_at DESC LIMIT 30"
        out = []
        for row in self._rows(sql):
            out.append({
                "scan_id": self._field(row, "a", 0),
                "instance": self._field(row, "b", 1),
                "operator": self._field(row, "c", 2),
                "summary": self._field(row, "d", 3),
                "findings": self._field(row, "e", 4),
            })
        return out


def market_radar_page(self) -> str:
    user = self._sess_user()
    if user is None:
        body = "".join([
            "<div class='card'><h2>Radar Transversal</h2>",
            "<p>Necesitas sesion.</p>",
            "</div>",
        ])
        return self._page_wrap("ZYRA MARKET - Radar", body)
    scans = self.rad.list_scans()
    s_rows = []
    for s in scans:
        s_rows.append(
            "<p>- <b>%s</b> (%s) %s hallazgos <code>%s</code></p>" % (
                s["instance"], s["operator"],
                str(s["findings"]), s["scan_id"]))
    if not s_rows:
        s_rows.append("<p>Sin escaneos.</p>")
    body = "".join([
        "<div class='card'><h2>Nuevo escaneo (MARKET)</h2>",
        "<input id='sSum' placeholder='Resumen del escaneo'>",
        "<input id='sLbl' placeholder='Etiqueta del hallazgo'>",
        "<input id='sScore' type='number' step='0.1' placeholder='Score 0-10'>",
        "<button id='btnScan'>Escanear y registrar</button>",
        "</div>",
        "<div class='card'><h2>Tokenizar un hallazgo</h2>",
        "<input id='tFin' placeholder='ID de hallazgo (FND-...)'>",
        "<button id='btnTok'>Tokenizar</button>",
        "".join(s_rows),
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
        ".then(function(d){if(d.ok){if(d.data&&d.data.findings!==undefined){",
        "document.getElementById('msg').textContent='Scan: '+JSON.stringify(d.data.findings);",
        "}else{location.reload();}}",
        "else{document.getElementById('msg').textContent='Error: '+(d.error||'');}})",
        ".catch(function(e){document.getElementById('msg').textContent='Error: '+e;});}",
        "document.getElementById('btnScan').addEventListener('click',function(){",
        "post('/subastas/api/radar',{action:'scan',instance:'market',",
        "summary:v('sSum'),",
        "findings:[{label:v('sLbl'),score:num('sScore')}]});});",
        "document.getElementById('btnTok').addEventListener('click',function(){",
        "post('/subastas/api/radar',{action:'tokenize',fin_id:v('tFin')});});",
        "</script>",
    ])
    return self._page_wrap("ZYRA MARKET - Radar", body)


def market_radar_api(self) -> None:
    try:
        user = self._sess_user()
        if user is None:
            self._send_json(401, {"ok": False, "error": "sesion requerida"})
            return
        account = user["username"]
        doc = self._read_json()
        if doc is None:
            self._send_json(400, {"ok": False, "error": "invalid JSON"})
            return
        action = str(doc.get("action", ""))
        if action == "scan":
            r = self.rad.scan(
                instance=str(doc.get("instance", "market")),
                operator=account,
                findings=doc.get("findings", []),
                summary=str(doc.get("summary", "")))
            self._send_json(201, {"ok": True, "data": r})
            return
        if action == "tokenize":
            r = self.rad.tokenize_finding(
                str(doc.get("fin_id", "")), operator=account)
            self._send_json(200, {"ok": True, "data": r})
            return
        if action == "list":
            r = self.rad.list_scans(doc.get("instance"))
            self._send_json(200, {"ok": True, "data": {"scans": r}})
            return
        self._send_json(400, {"ok": False, "error": "accion desconocida"})
    except Exception:
        self._send_json(500, {
            "ok": False, "error": "server error",
            "trace": traceback.format_exc(),
        })
