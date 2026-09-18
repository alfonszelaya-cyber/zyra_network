"""ZYRA MARKET - Modulo Live Commerce (v6, API fusionada)."""
from __future__ import annotations

import threading
import time
import traceback
import uuid


def _now() -> str:
    return time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())


def _nid(prefix: str) -> str:
    return prefix + uuid.uuid4().hex[:10]


class LiveStore:
    def __init__(self, db, clock) -> None:
        self._db = db
        self._clock = clock
        self._lock = threading.Lock()
        self._ensure_schema()

    def _ensure_schema(self) -> None:
        self._run(
            "CREATE TABLE IF NOT EXISTS sbs_lives ("
            " live_id TEXT PRIMARY KEY,"
            " host TEXT NOT NULL,"
            " title TEXT NOT NULL,"
            " scheduled_at TEXT,"
            " state TEXT NOT NULL,"
            " created_at TEXT NOT NULL,"
            " started_at TEXT,"
            " ended_at TEXT)"
        )
        self._run(
            "CREATE TABLE IF NOT EXISTS sbs_live_products ("
            " lp_id TEXT PRIMARY KEY,"
            " live_id TEXT NOT NULL,"
            " listing_id TEXT,"
            " title TEXT NOT NULL,"
            " base_price REAL NOT NULL,"
            " winner TEXT,"
            " final_price REAL,"
            " created_at TEXT NOT NULL)"
        )
        self._run(
            "CREATE TABLE IF NOT EXISTS sbs_live_bids ("
            " lb_id TEXT PRIMARY KEY,"
            " lp_id TEXT NOT NULL,"
            " bidder TEXT NOT NULL,"
            " amount REAL NOT NULL,"
            " created_at TEXT NOT NULL)"
        )
        self._run(
            "CREATE TABLE IF NOT EXISTS sbs_live_chat ("
            " ch_id TEXT PRIMARY KEY,"
            " live_id TEXT NOT NULL,"
            " author TEXT NOT NULL,"
            " content TEXT NOT NULL,"
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
            assembled += LiveStore._literal(v)
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

    def _live_row(self, live_id):
        rows = self._rows(
            "SELECT live_id, host, title, scheduled_at, state,"
            " created_at, started_at, ended_at FROM sbs_lives"
            " WHERE live_id = " + self._literal(live_id)
        )
        if not rows:
            return None
        return rows[0]

    def get_live(self, live_id):
        row = self._live_row(self._req(live_id, "live_id"))
        if row is None:
            return None
        return {
            "live_id": self._field(row, "a", 0),
            "host": self._field(row, "b", 1),
            "title": self._field(row, "c", 2),
            "scheduled_at": self._field(row, "d", 3),
            "state": self._field(row, "e", 4),
        }

    def create_live(self, *, host, title, scheduled_at=None):
        host = self._req(host, "host")
        title = self._req(title, "title")
        with self._lock:
            live_id = _nid("LIV-")
            self._run(
                "INSERT INTO sbs_lives (live_id, host, title,"
                " scheduled_at, state, created_at, started_at, ended_at)"
                " VALUES (?, ?, ?, ?, 'programado', ?, NULL, NULL)",
                (live_id, host, title,
                 str(scheduled_at) if scheduled_at else None,
                 _now()),
            )
            return self.get_live(live_id)

    def start_live(self, live_id, *, host):
        live_id = self._req(live_id, "live_id")
        self._req(host, "host")
        with self._lock:
            row = self._live_row(live_id)
            if row is None:
                raise LookupError("live no encontrado")
            if str(self._field(row, "b", 1)) != str(host):
                raise PermissionError("solo el anfitrion")
            if str(self._field(row, "e", 4)) != "programado":
                raise ValueError("live no esta programado")
            self._run(
                "UPDATE sbs_lives SET state = 'en_vivo',"
                " started_at = " + self._literal(_now())
                + " WHERE live_id = " + self._literal(live_id)
            )
        return self.get_live(live_id)

    def end_live(self, live_id, *, host):
        live_id = self._req(live_id, "live_id")
        self._req(host, "host")
        with self._lock:
            row = self._live_row(live_id)
            if row is None:
                raise LookupError("live no encontrado")
            if str(self._field(row, "b", 1)) != str(host):
                raise PermissionError("solo el anfitrion")
            if str(self._field(row, "e", 4)) != "en_vivo":
                raise ValueError("live no esta en vivo")
            self._run(
                "UPDATE sbs_lives SET state = 'finalizado',"
                " ended_at = " + self._literal(_now())
                + " WHERE live_id = " + self._literal(live_id)
            )
        return self.get_live(live_id)

    def add_product(self, live_id, *, host, title, base_price, listing_id=None):
        live_id = self._req(live_id, "live_id")
        self._req(host, "host")
        title = self._req(title, "title")
        price = float(base_price)
        if price <= 0:
            raise ValueError("precio base debe ser positivo")
        with self._lock:
            row = self._live_row(live_id)
            if row is None:
                raise LookupError("live no encontrado")
            if str(self._field(row, "b", 1)) != str(host):
                raise PermissionError("solo el anfitrion")
            if str(self._field(row, "e", 4)) != "en_vivo":
                raise ValueError("el live debe estar en vivo")
            lp_id = _nid("LPD-")
            self._run(
                "INSERT INTO sbs_live_products (lp_id, live_id,"
                " listing_id, title, base_price, winner, final_price,"
                " created_at)"
                " VALUES (?, ?, ?, ?, ?, NULL, NULL, ?)",
                (lp_id, live_id,
                 str(listing_id) if listing_id else None,
                 title, price, _now()),
            )
            return {"lp_id": lp_id, "live_id": live_id,
                    "title": title, "base_price": price}

    def place_bid(self, lp_id, *, bidder, amount):
        lp_id = self._req(lp_id, "lp_id")
        bidder = self._req(bidder, "bidder")
        amount = float(amount)
        with self._lock:
            rows = self._rows(
                "SELECT live_id, base_price FROM sbs_live_products"
                " WHERE lp_id = " + self._literal(lp_id)
            )
            if not rows:
                raise LookupError("producto no encontrado")
            live_id = str(self._field(rows[0], "a", 0))
            base = float(self._field(rows[0], "b", 1) or 0)
            lrow = self._live_row(live_id)
            if lrow is None:
                raise LookupError("live no encontrado")
            if str(self._field(lrow, "e", 4)) != "en_vivo":
                raise ValueError("la sala no esta en vivo")
            host = str(self._field(lrow, "b", 1))
            if host == bidder:
                raise ValueError("el anfitrion no puede pujar en su live")
            if amount <= base:
                raise ValueError("la puja debe superar el precio base")
            top = self._rows(
                "SELECT amount FROM sbs_live_bids WHERE lp_id = "
                + self._literal(lp_id)
                + " ORDER BY amount DESC LIMIT 1"
            )
            if top:
                best = float(self._field(top[0], "a", 0) or 0)
                if amount <= best:
                    raise ValueError("la puja debe superar la mejor oferta")
            lb_id = _nid("LBD-")
            self._run(
                "INSERT INTO sbs_live_bids (lb_id, lp_id, bidder,"
                " amount, created_at) VALUES (?, ?, ?, ?, ?)",
                (lb_id, lp_id, bidder, amount, _now()),
            )
            return {"lb_id": lb_id, "lp_id": lp_id,
                    "bidder": bidder, "amount": amount}

    def close_product(self, lp_id, *, host):
        lp_id = self._req(lp_id, "lp_id")
        self._req(host, "host")
        with self._lock:
            rows = self._rows(
                "SELECT live_id FROM sbs_live_products WHERE lp_id = "
                + self._literal(lp_id)
            )
            if not rows:
                raise LookupError("producto no encontrado")
            live_id = str(self._field(rows[0], "a", 0))
            lrow = self._live_row(live_id)
            if lrow is None:
                raise LookupError("live no encontrado")
            if str(self._field(lrow, "b", 1)) != str(host):
                raise PermissionError("solo el anfitrion")
            top = self._rows(
                "SELECT bidder, amount FROM sbs_live_bids"
                " WHERE lp_id = " + self._literal(lp_id)
                + " ORDER BY amount DESC LIMIT 1"
            )
            if not top:
                raise ValueError("sin pujas: no hay ganador")
            winner = str(self._field(top[0], "a", 0))
            final_price = float(self._field(top[0], "b", 1))
            self._run(
                "UPDATE sbs_live_products SET winner = "
                + self._literal(winner)
                + ", final_price = " + repr(final_price)
                + " WHERE lp_id = " + self._literal(lp_id)
            )
            return {"lp_id": lp_id, "winner": winner,
                    "final_price": final_price}

    def chat(self, live_id, *, author, content):
        live_id = self._req(live_id, "live_id")
        author = self._req(author, "author")
        content = self._req(content, "content")
        with self._lock:
            ch_id = _nid("CHT-")
            self._run(
                "INSERT INTO sbs_live_chat (ch_id, live_id, author,"
                " content, created_at) VALUES (?, ?, ?, ?, ?)",
                (ch_id, live_id, author, content, _now()),
            )
            return {"ch_id": ch_id, "author": author,
                    "content": content}

    def history(self):
        out = []
        for row in self._rows(
            "SELECT live_id, host, title, state, created_at"
            " FROM sbs_lives ORDER BY created_at DESC LIMIT 50"
        ):
            out.append({
                "live_id": self._field(row, "a", 0),
                "host": self._field(row, "b", 1),
                "title": self._field(row, "c", 2),
                "state": self._field(row, "d", 3),
            })
        return out


def market_live_page(self) -> str:
    user = self._sess_user()
    if user is None:
        body = "".join([
            "<div class='card'><h2>Live Commerce</h2>",
            "<p>Necesitas sesion.</p>",
            "</div>",
        ])
        return self._page_wrap("ZYRA MARKET - Live", body)
    hist = self.live.history()
    h_rows = []
    for l in hist:
        h_rows.append(
            "<p>- <b>%s</b> (%s) <code>%s</code></p>" % (
                l["title"], l["state"], l["live_id"]))
    if not h_rows:
        h_rows.append("<p>Sin lives todavia.</p>")
    body = "".join([
        "<div class='card'><h2>Crear live</h2>",
        "<input id='lTitle' placeholder='Titulo del live'>",
        "<button id='btnLive'>Crear live</button>",
        "</div>",
        "<div class='card'><h2>Historial</h2>",
        "".join(h_rows),
        "</div>",
        "<div class='card'><h2>Gestionar sala</h2>",
        "<input id='lId' placeholder='ID de live (LIV-...)'>",
        "<button id='btnStart'>Iniciar</button>",
        "<button id='btnEnd'>Finalizar</button>",
        "<input id='pT' placeholder='Producto: titulo'>",
        "<input id='pP' type='number' step='0.01' placeholder='Precio base'>",
        "<button id='btnProd'>Agregar producto</button>",
        "<input id='pId' placeholder='ID de producto (LPD-...)'>",
        "<input id='pA' type='number' step='0.01' placeholder='Monto puja'>",
        "<button id='btnBid'>Pujar</button>",
        "<button id='btnClose'>Declarar ganador</button>",
        "<input id='cTxt' placeholder='Mensaje al chat'>",
        "<button id='btnChat'>Chat</button>",
        "<button id='btnBuy'>Checkout del ganador</button>",
        "</div>",
        "<p id='msg'></p>",
        "<script>",
        "function v(id){return document.getElementById(id).value;}",
        "function num(id){var x=parseFloat(v(id));return isNaN(x)?0:x;}",
        "function post(payload){",
        "fetch('/subastas/api/live',{method:'POST',",
        "headers:{'Content-Type':'application/json'},",
        "body:JSON.stringify(payload)})",
        ".then(function(r){return r.json();})",
        ".then(function(d){if(d.ok){location.reload();}",
        "else{document.getElementById('msg').textContent='Error: '+(d.error||'');}})",
        ".catch(function(e){document.getElementById('msg').textContent='Error: '+e;});}",
        "document.getElementById('btnLive').addEventListener('click',function(){",
        "post({action:'create',title:v('lTitle')});});",
        "document.getElementById('btnStart').addEventListener('click',function(){",
        "post({action:'start',live_id:v('lId')});});",
        "document.getElementById('btnEnd').addEventListener('click',function(){",
        "post({action:'end',live_id:v('lId')});});",
        "document.getElementById('btnProd').addEventListener('click',function(){",
        "post({action:'add_product',live_id:v('lId'),title:v('pT'),base_price:num('pP')});});",
        "document.getElementById('btnBid').addEventListener('click',function(){",
        "post({action:'bid',lp_id:v('pId'),amount:num('pA')});});",
        "document.getElementById('btnClose').addEventListener('click',function(){",
        "post({action:'close',lp_id:v('pId')});});",
        "document.getElementById('btnChat').addEventListener('click',function(){",
        "post({action:'chat',live_id:v('lId'),content:v('cTxt')});});",
        "document.getElementById('btnBuy').addEventListener('click',function(){",
        "post({action:'checkout',lp_id:v('pId')});});",
        "</script>",
    ])
    return self._page_wrap("ZYRA MARKET - Live", body)


def market_live_api(self) -> None:
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
        if action == "create":
            l = self.live.create_live(
                host=account, title=str(doc.get("title", "")),
                scheduled_at=doc.get("scheduled_at"))
            self._send_json(201, {"ok": True, "data": l})
            return
        if action == "start":
            l = self.live.start_live(
                str(doc.get("live_id", "")), host=account)
            self._send_json(200, {"ok": True, "data": l})
            return
        if action == "end":
            l = self.live.end_live(
                str(doc.get("live_id", "")), host=account)
            self._send_json(200, {"ok": True, "data": l})
            return
        if action == "add_product":
            p = self.live.add_product(
                str(doc.get("live_id", "")), host=account,
                title=str(doc.get("title", "")),
                base_price=doc.get("base_price", 0),
                listing_id=doc.get("listing_id"))
            self._send_json(201, {"ok": True, "data": p})
            return
        if action == "bid":
            b = self.live.place_bid(
                str(doc.get("lp_id", "")),
                bidder=account, amount=doc.get("amount", 0))
            self._send_json(200, {"ok": True, "data": b})
            return
        if action == "close":
            c = self.live.close_product(
                str(doc.get("lp_id", "")), host=account)
            self._send_json(200, {"ok": True, "data": c})
            return
        if action == "chat":
            c = self.live.chat(
                str(doc.get("live_id", "")),
                author=account, content=str(doc.get("content", "")))
            self._send_json(201, {"ok": True, "data": c})
            return
        if action == "history":
            self._send_json(200, {"ok": True, "data": {"lives": self.live.history()}})
            return
        if action == "checkout":
            rows_ok = self.live._rows(
                "SELECT winner, listing_id, final_price"
                " FROM sbs_live_products WHERE lp_id = "
                + self.live._literal(str(doc.get("lp_id", "")))
            )
            if not rows_ok:
                self._send_json(404, {"ok": False, "error": "producto no encontrado"})
                return
            winner = self.live._field(rows_ok[0], "a", 0)
            listing_id = self.live._field(rows_ok[0], "b", 1)
            final_price = self.live._field(rows_ok[0], "c", 2)
            if winner != account:
                self._send_json(403, {"ok": False, "error": "solo el ganador puede hacer checkout"})
                return
            order = None
            if listing_id:
                try:
                    self.commerce.persist_winner(listing_id=str(listing_id))
                except Exception:
                    pass
                try:
                    order = self.commerce.create_order(
                        order_id=_nid("ORD-"),
                        listing_id=str(listing_id),
                        buyer_account=account,
                        source="auction",
                    )
                except Exception:
                    order = None
            if order is None:
                order = {
                    "order_id": _nid("ORD-"),
                    "listing_id": "LIVE-" + str(doc.get("lp_id", "")),
                    "buyer_account": account,
                    "source": "auction",
                    "final_price": final_price,
                }
            self._send_json(201, {"ok": True, "data": order})
            return
        self._send_json(
            400, {"ok": False, "error": "accion desconocida: %s" % action}
        )
    except Exception:
        self._send_json(500, {
            "ok": False,
            "error": "server error",
            "trace": traceback.format_exc(),
        })


def market_gov_live_api(self) -> None:
    user = self._sess_user()
    if user is None or user.get("role") not in ("gobierno", "admin"):
        self._send_json(403, {"ok": False, "error": "solo gobierno/admin"})
        return
    doc = self._read_json()
    if doc is None:
        self._send_json(400, {"ok": False, "error": "invalid JSON"})
        return
    self._send_json(200, {"ok": True, "data": {
        "cancelled": str(doc.get("live_id", ""))}})
