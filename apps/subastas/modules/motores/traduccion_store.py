"""MOTOR TRADUCCION - diccionario extensible ES/EN."""
from __future__ import annotations

import threading
import time
import traceback
import uuid


def _now() -> str:
    return time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())


def _nid(prefix: str) -> str:
    return prefix + uuid.uuid4().hex[:10]


class TraduccionStore:
    def __init__(self, db, clock) -> None:
        self._db = db
        self._clock = clock
        self._lock = threading.RLock()
        self._ensure_schema()

    def _ensure_schema(self) -> None:
        self._run(
            "CREATE TABLE IF NOT EXISTS sbs_translations ("
            " tr_id TEXT PRIMARY KEY,"
            " src_text TEXT NOT NULL,"
            " src_lang TEXT NOT NULL,"
            " dst_lang TEXT NOT NULL,"
            " dst_text TEXT NOT NULL,"
            " added_by TEXT NOT NULL,"
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
            assembled += TraduccionStore._literal(v)
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

    def add_pair(self, *, src_text, src_lang, dst_lang, dst_text, by):
        src_text = str(src_text or "").strip().lower()
        src_lang = str(src_lang or "").strip().lower()
        dst_lang = str(dst_lang or "").strip().lower()
        dst_text = str(dst_text or "").strip()
        if not src_text or not dst_text:
            raise ValueError("textos obligatorios")
        if src_lang not in ("es", "en") or dst_lang not in ("es", "en"):
            raise ValueError("idiomas soportados: es, en")
        if src_lang == dst_lang:
            raise ValueError("idiomas no pueden ser iguales")
        with self._lock:
            tr_id = _nid("TRN-")
            self._run(
                "INSERT INTO sbs_translations (tr_id, src_text,"
                " src_lang, dst_lang, dst_text, added_by, created_at)"
                " VALUES (?, ?, ?, ?, ?, ?, ?)",
                (tr_id, src_text, src_lang, dst_lang,
                 dst_text, by, _now()),
            )
            return {"tr_id": tr_id, "src": src_text, "dst": dst_text}

    def translate(self, text, *, from_lang, to_lang):
        text = str(text or "").strip()
        from_lang = str(from_lang or "").strip().lower()
        to_lang = str(to_lang or "").strip().lower()
        words = text.split()
        out_words = []
        hits = 0
        misses = 0
        for w in words:
            wl = w.lower().strip(".,!?")
            rows = self._rows(
                "SELECT dst_text FROM sbs_translations"
                " WHERE src_text = " + self._literal(wl)
                + " AND src_lang = " + self._literal(from_lang)
                + " AND dst_lang = " + self._literal(to_lang)
                + " LIMIT 1"
            )
            if rows:
                out_words.append(str(self._field(rows[0], "a", 0)))
                hits += 1
            else:
                out_words.append(w)
                misses += 1
        return {
            "original": text,
            "translated": " ".join(out_words),
            "from": from_lang, "to": to_lang,
            "hits": hits, "misses": misses,
        }


def market_gov_traduccion_page(self) -> str:
    user = self._sess_user()
    if user is None or user.get("role") not in ("gobierno", "admin"):
        body = "<p>Solo gobierno/admin.</p>"
        return self._page_wrap("ZYRA MARKET - Gov Traduccion", body)
    body = "".join([
        "<div class='card'><h2>Agregar par de traduccion</h2>",
        "<input id='tSrc' placeholder='Texto origen (ej. hello)'>",
        "<select id='tFrom'><option value='en'>en</option><option value='es'>es</option></select>",
        "<select id='tTo'><option value='es'>es</option><option value='en'>en</option></select>",
        "<input id='tDst' placeholder='Traduccion (ej. hola)'>",
        "<button id='btnTr'>Guardar par</button>",
        "</div>",
        "<p id='msg'></p>",
        "<script>",
        "document.getElementById('btnTr').addEventListener('click',function(){",
        "function g(i){return document.getElementById(i).value;}",
        "fetch('/subastas/api/gov-traduccion',{method:'POST',",
        "headers:{'Content-Type':'application/json'},",
        "body:JSON.stringify({src_text:g('tSrc'),src_lang:g('tFrom'),dst_lang:g('tTo'),dst_text:g('tDst')})})",
        ".then(function(r){return r.json();})",
        ".then(function(d){if(d.ok){location.reload();}",
        "else{document.getElementById('msg').textContent='Error: '+(d.error||'');}})",
        ".catch(function(e){document.getElementById('msg').textContent='Error: '+e;});});",
        "</script>",
    ])
    return self._page_wrap("ZYRA MARKET - Gov Traduccion", body)


def market_traduccion_api(self) -> None:
    try:
        user = self._sess_user()
        if user is None:
            self._send_json(401, {"ok": False, "error": "sesion requerida"})
            return
        doc = self._read_json()
        if doc is None:
            self._send_json(400, {"ok": False, "error": "invalid JSON"})
            return
        action = str(doc.get("action", ""))
        if action == "translate":
            r = self.trn.translate(
                str(doc.get("text", "")),
                from_lang=str(doc.get("from", "en")),
                to_lang=str(doc.get("to", "es")))
            self._send_json(200, {"ok": True, "data": r})
            return
        self._send_json(400, {"ok": False, "error": "accion desconocida"})
    except Exception:
        self._send_json(500, {
            "ok": False, "error": "server error",
            "trace": traceback.format_exc(),
        })


def market_gov_traduccion_api(self) -> None:
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
        if action == "add_pair":
            r = self.trn.add_pair(
                src_text=str(doc.get("src_text", "")),
                src_lang=str(doc.get("src_lang", "en")),
                dst_lang=str(doc.get("dst_lang", "es")),
                dst_text=str(doc.get("dst_text", "")),
                by=user["username"])
            self._send_json(201, {"ok": True, "data": r})
            return
        self._send_json(400, {"ok": False, "error": "accion desconocida"})
    except Exception:
        self._send_json(500, {
            "ok": False, "error": "server error",
            "trace": traceback.format_exc(),
        })
