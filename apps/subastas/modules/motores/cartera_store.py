"""MOTOR CARTERA - Traslacion de dinero (NO banco). RLock."""
from __future__ import annotations

import threading
import time
import traceback
import uuid


def _now() -> str:
    return time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())


def _nid(prefix: str) -> str:
    return prefix + uuid.uuid4().hex[:10]


class CarteraStore:
    def __init__(self, db, clock) -> None:
        self._db = db
        self._clock = clock
        self._lock = threading.RLock()
        self._ensure_schema()

    def _ensure_schema(self) -> None:
        self._run(
            "CREATE TABLE IF NOT EXISTS sbs_wallet ("
            " wal_id TEXT PRIMARY KEY,"
            " account TEXT UNIQUE NOT NULL,"
            " balance REAL NOT NULL DEFAULT 0,"
            " currency TEXT NOT NULL DEFAULT 'USD',"
            " created_at TEXT NOT NULL,"
            " updated_at TEXT NOT NULL)"
        )
        self._run(
            "CREATE TABLE IF NOT EXISTS sbs_wallet_moves ("
            " mov_id TEXT PRIMARY KEY,"
            " account TEXT NOT NULL,"
            " kind TEXT NOT NULL,"
            " amount REAL NOT NULL,"
            " counterparty TEXT,"
            " note TEXT,"
            " created_at TEXT NOT NULL)"
        )
        self._run(
            "CREATE TABLE IF NOT EXISTS sbs_fx_rates ("
            " fx_id TEXT PRIMARY KEY,"
            " from_cur TEXT NOT NULL,"
            " to_cur TEXT NOT NULL,"
            " rate REAL NOT NULL,"
            " updated_by TEXT NOT NULL,"
            " updated_at TEXT NOT NULL)"
        )
        self._run(
            "CREATE TABLE IF NOT EXISTS sbs_escrow ("
            " esc_id TEXT PRIMARY KEY,"
            " order_ref TEXT NOT NULL,"
            " from_a TEXT NOT NULL,"
            " to_a TEXT NOT NULL,"
            " amount REAL NOT NULL,"
            " status TEXT NOT NULL,"
            " created_at TEXT NOT NULL,"
            " released_at TEXT)"
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
            assembled += CarteraStore._literal(v)
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

    def _wallet(self, account):
        rows = self._rows(
            "SELECT wal_id, balance, currency FROM sbs_wallet"
            " WHERE account = " + self._literal(account)
        )
        if not rows:
            return None
        return {
            "wal_id": self._field(rows[0], "a", 0),
            "account": account,
            "balance": float(self._field(rows[0], "b", 1) or 0),
            "currency": self._field(rows[0], "c", 2),
        }

    def _ensure_wallet_nolock(self, account, currency="USD"):
        w = self._wallet(account)
        if w is not None:
            return w
        wal_id = _nid("WAL-")
        now = _now()
        self._run(
            "INSERT INTO sbs_wallet (wal_id, account, balance,"
            " currency, created_at, updated_at)"
            " VALUES (?, ?, 0, ?, ?, ?)",
            (wal_id, account, str(currency or "USD"), now, now),
        )
        return self._wallet(account)

    def open_wallet(self, account, currency="USD"):
        account = self._req(account, "account")
        with self._lock:
            return self._ensure_wallet_nolock(account, currency)

    def balance(self, account):
        w = self._wallet(self._req(account, "account"))
        if w is None:
            return {"account": account, "balance": 0.0,
                    "currency": "USD"}
        return {"account": account, "balance": w["balance"],
                "currency": w["currency"]}

    def _move(self, account, kind, amount, counterparty=None, note=None):
        self._run(
            "INSERT INTO sbs_wallet_moves (mov_id, account, kind,"
            " amount, counterparty, note, created_at)"
            " VALUES (?, ?, ?, ?, ?, ?, ?)",
            (_nid("MOV-"), account, kind, float(amount),
             str(counterparty) if counterparty else None,
             str(note) if note else None, _now()),
        )

    def deposit(self, account, amount, note=None):
        account = self._req(account, "account")
        amt = float(amount)
        if amt <= 0:
            raise ValueError("monto debe ser positivo")
        with self._lock:
            self._ensure_wallet_nolock(account)
            w = self._wallet(account)
            new_bal = w["balance"] + amt
            self._run(
                "UPDATE sbs_wallet SET balance = " + repr(new_bal)
                + ", updated_at = " + self._literal(_now())
                + " WHERE account = " + self._literal(account)
            )
            self._move(account, "deposito", amt, None, note)
            return self.balance(account)

    def transfer(self, *, from_a, to_a, amount, note=None):
        from_a = self._req(from_a, "from_a")
        to_a = self._req(to_a, "to_a")
        amt = float(amount)
        if amt <= 0:
            raise ValueError("monto debe ser positivo")
        if from_a == to_a:
            raise ValueError("no puedes transferirte a ti mismo")
        with self._lock:
            w = self._wallet(from_a)
            if w is None:
                raise LookupError("cartera origen no existe")
            if w["balance"] < amt:
                raise ValueError("saldo insuficiente")
            self._ensure_wallet_nolock(to_a)
            nb_from = w["balance"] - amt
            self._run(
                "UPDATE sbs_wallet SET balance = " + repr(nb_from)
                + ", updated_at = " + self._literal(_now())
                + " WHERE account = " + self._literal(from_a)
            )
            self._run(
                "UPDATE sbs_wallet SET balance = balance + " + repr(amt)
                + ", updated_at = " + self._literal(_now())
                + " WHERE account = " + self._literal(to_a)
            )
            self._move(from_a, "envio", -amt, to_a, note)
            self._move(to_a, "recibo", amt, from_a, note)
            return self.balance(from_a)

    def set_rate(self, *, from_cur, to_cur, rate, by):
        from_cur = self._req(from_cur, "from_cur").upper()
        to_cur = self._req(to_cur, "to_cur").upper()
        rate = float(rate)
        if rate <= 0:
            raise ValueError("tasa debe ser positiva")
        with self._lock:
            row = self._rows(
                "SELECT fx_id FROM sbs_fx_rates WHERE from_cur = "
                + self._literal(from_cur)
                + " AND to_cur = " + self._literal(to_cur)
            )
            if row:
                fx_id = str(self._field(row[0], "a", 0))
                self._run(
                    "UPDATE sbs_fx_rates SET rate = " + repr(rate)
                    + ", updated_by = " + self._literal(by)
                    + ", updated_at = " + self._literal(_now())
                    + " WHERE fx_id = " + self._literal(fx_id)
                )
            else:
                fx_id = _nid("FX-")
                self._run(
                    "INSERT INTO sbs_fx_rates (fx_id, from_cur,"
                    " to_cur, rate, updated_by, updated_at)"
                    " VALUES (?, ?, ?, ?, ?, ?)",
                    (fx_id, from_cur, to_cur, rate, by, _now()),
                )
            return {"fx_id": fx_id, "from": from_cur,
                    "to": to_cur, "rate": rate}

    def convert(self, amount, *, from_cur, to_cur):
        from_cur = self._req(from_cur, "from_cur").upper()
        to_cur = self._req(to_cur, "to_cur").upper()
        amt = float(amount)
        if from_cur == to_cur:
            return {"amount": amt, "rate": 1.0,
                    "from": from_cur, "to": to_cur}
        rows = self._rows(
            "SELECT rate FROM sbs_fx_rates WHERE from_cur = "
            + self._literal(from_cur)
            + " AND to_cur = " + self._literal(to_cur)
        )
        if not rows:
            raise LookupError(
                "tasa %s a %s no configurada" % (from_cur, to_cur))
        rate = float(self._field(rows[0], "a", 0))
        return {"amount": round(amt * rate, 6), "rate": rate,
                "from": from_cur, "to": to_cur}

    def escrow_hold(self, *, order_ref, from_a, to_a, amount):
        order_ref = self._req(order_ref, "order_ref")
        from_a = self._req(from_a, "from_a")
        to_a = self._req(to_a, "to_a")
        amt = float(amount)
        if amt <= 0:
            raise ValueError("monto debe ser positivo")
        with self._lock:
            w = self._wallet(from_a)
            if w is None:
                raise LookupError("cartera origen no existe")
            if w["balance"] < amt:
                raise ValueError("saldo insuficiente para escrow")
            nb = w["balance"] - amt
            self._run(
                "UPDATE sbs_wallet SET balance = " + repr(nb)
                + ", updated_at = " + self._literal(_now())
                + " WHERE account = " + self._literal(from_a)
            )
            esc_id = _nid("ESC-")
            self._run(
                "INSERT INTO sbs_escrow (esc_id, order_ref, from_a,"
                " to_a, amount, status, created_at, released_at)"
                " VALUES (?, ?, ?, ?, ?, 'held', ?, NULL)",
                (esc_id, order_ref, from_a, to_a, amt, _now()),
            )
            self._move(from_a, "escrow_retencion", -amt, to_a, order_ref)
            return {"esc_id": esc_id, "status": "held",
                    "amount": amt}

    def escrow_release(self, esc_id):
        esc_id = self._req(esc_id, "esc_id")
        with self._lock:
            rows = self._rows(
                "SELECT to_a, amount, status FROM sbs_escrow"
                " WHERE esc_id = " + self._literal(esc_id)
            )
            if not rows:
                raise LookupError("escrow no encontrado")
            status = str(self._field(rows[0], "c", 2))
            if status != "held":
                raise ValueError("escrow no esta retenido")
            to_a = str(self._field(rows[0], "a", 0))
            amt = float(self._field(rows[0], "b", 1))
            self._ensure_wallet_nolock(to_a)
            self._run(
                "UPDATE sbs_wallet SET balance = balance + " + repr(amt)
                + ", updated_at = " + self._literal(_now())
                + " WHERE account = " + self._literal(to_a)
            )
            self._run(
                "UPDATE sbs_escrow SET status = 'released',"
                " released_at = " + self._literal(_now())
                + " WHERE esc_id = " + self._literal(esc_id)
            )
            self._move(to_a, "escrow_liberacion", amt, None, esc_id)
            return {"esc_id": esc_id, "status": "released",
                    "amount": amt}

    def moves_for(self, account, limit=30):
        account = self._req(account, "account")
        out = []
        for row in self._rows(
            "SELECT mov_id, kind, amount, counterparty, note, created_at"
            " FROM sbs_wallet_moves WHERE account = "
            + self._literal(account)
            + " ORDER BY created_at DESC LIMIT " + str(int(limit))
        ):
            out.append({
                "mov_id": self._field(row, "a", 0),
                "kind": self._field(row, "b", 1),
                "amount": self._field(row, "c", 2),
                "counterparty": self._field(row, "d", 3),
                "note": self._field(row, "e", 4),
                "created_at": self._field(row, "f", 5),
            })
        return out


def market_cartera_page(self) -> str:
    user = self._sess_user()
    if user is None:
        body = "".join([
            "<div class='card'><h2>Cartera</h2>",
            "<p>Necesitas sesion.</p>",
            "<p><a href='/subastas/inscripcion'><button>Entrar</button></a></p>",
            "</div>",
        ])
        return self._page_wrap("ZYRA MARKET - Cartera", body)
    account = user["username"]
    bal = self.car.balance(account)
    moves = self.car.moves_for(account)
    m_rows = []
    for m in moves:
        m_rows.append(
            "<p>- [%s] %s: $%s (%s)</p>" % (
                m["created_at"], m["kind"],
                format(float(m["amount"] or 0), ".2f"),
                m["counterparty"] or m["note"] or "-"))
    if not m_rows:
        m_rows.append("<p>Sin movimientos.</p>")
    body = "".join([
        "<div class='card'><h2>Mi Cartera</h2>",
        "<p>Saldo: <b>$%s</b> (%s)</p>" % (
            format(float(bal["balance"]), ".2f"), bal["currency"]),
        "<p>MOTOR CARTERA: traslacion de dinero, no somos banco.</p>",
        "</div>",
        "<div class='card'><h2>Enviar dinero</h2>",
        "<input id='wTo' placeholder='Cuenta destino'>",
        "<input id='wAmt' type='number' step='0.01' placeholder='Monto'>",
        "<input id='wNote' placeholder='Nota'>",
        "<button id='btnSend'>Enviar</button>",
        "</div>",
        "<div class='card'><h2>Recargar</h2>",
        "<input id='dAmt' type='number' step='0.01' placeholder='Monto'>",
        "<button id='btnDep'>Depositar</button>",
        "</div>",
        "<div class='card'><h2>Convertir moneda</h2>",
        "<input id='cAmt' type='number' step='0.01' placeholder='Monto'>",
        "<input id='cFrom' placeholder='De (USD/BTC/QTZ)'>",
        "<input id='cTo' placeholder='A (USD/BTC/QTZ)'>",
        "<button id='btnConv'>Convertir</button>",
        "</div>",
        "<div class='card'><h2>Movimientos</h2>",
        "".join(m_rows),
        "</div>",
        "<p id='msg'></p>",
        "<script>",
        "function v(id){return document.getElementById(id).value;}",
        "function num(id){var x=parseFloat(v(id));return isNaN(x)?0:x;}",
        "function post(payload){",
        "fetch('/subastas/api/cartera',{method:'POST',",
        "headers:{'Content-Type':'application/json'},",
        "body:JSON.stringify(payload)})",
        ".then(function(r){return r.json();})",
        ".then(function(d){if(d.ok){if(d.data&&d.data.converted){",
        "document.getElementById('msg').textContent='Convertido: '+d.data.converted.amount;",
        "}else{location.reload();}}",
        "else{document.getElementById('msg').textContent='Error: '+(d.error||'');}})",
        ".catch(function(e){document.getElementById('msg').textContent='Error: '+e;});}",
        "document.getElementById('btnSend').addEventListener('click',function(){",
        "post({action:'transfer',to:v('wTo'),amount:num('wAmt'),note:v('wNote')});});",
        "document.getElementById('btnDep').addEventListener('click',function(){",
        "post({action:'deposit',amount:num('dAmt')});});",
        "document.getElementById('btnConv').addEventListener('click',function(){",
        "post({action:'convert',amount:num('cAmt'),from:v('cFrom'),to:v('cTo')});});",
        "</script>",
    ])
    return self._page_wrap("ZYRA MARKET - Cartera", body)


def market_gov_cartera_page(self) -> str:
    user = self._sess_user()
    if user is None or user.get("role") not in ("gobierno", "admin"):
        body = "<p>Solo gobierno/admin.</p>"
        return self._page_wrap("ZYRA MARKET - Gov Cartera", body)
    body = "".join([
        "<div class='card'><h2>Tasas de cambio</h2>",
        "<input id='fFrom' placeholder='De (ej. USD)'>",
        "<input id='fTo' placeholder='A (ej. BTC)'>",
        "<input id='fRate' type='number' step='0.0001' placeholder='Tasa'>",
        "<button id='btnRate'>Guardar tasa</button>",
        "</div>",
        "<p id='msg'></p>",
        "<script>",
        "document.getElementById('btnRate').addEventListener('click',function(){",
        "function g(i){return document.getElementById(i).value;}",
        "fetch('/subastas/api/gov-cartera',{method:'POST',",
        "headers:{'Content-Type':'application/json'},",
        "body:JSON.stringify({action:'set_rate',from_cur:g('fFrom'),to_cur:g('fTo'),rate:parseFloat(g('fRate'))})})",
        ".then(function(r){return r.json();})",
        ".then(function(d){if(d.ok){location.reload();}",
        "else{document.getElementById('msg').textContent='Error: '+(d.error||'');}})",
        ".catch(function(e){document.getElementById('msg').textContent='Error: '+e;});});",
        "</script>",
    ])
    return self._page_wrap("ZYRA MARKET - Gov Cartera", body)


def market_cartera_api(self) -> None:
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
        if action == "open":
            w = self.car.open_wallet(account)
            self._send_json(200, {"ok": True, "data": w})
            return
        if action == "balance":
            self._send_json(200, {"ok": True, "data": self.car.balance(account)})
            return
        if action == "deposit":
            b = self.car.deposit(account, doc.get("amount", 0),
                                 note=doc.get("note"))
            self._send_json(200, {"ok": True, "data": b})
            return
        if action == "transfer":
            b = self.car.transfer(
                from_a=account, to_a=str(doc.get("to", "")),
                amount=doc.get("amount", 0), note=doc.get("note"))
            self._send_json(200, {"ok": True, "data": b})
            return
        if action == "convert":
            r = self.car.convert(
                doc.get("amount", 0),
                from_cur=str(doc.get("from", "USD")),
                to_cur=str(doc.get("to", "USD")))
            r["converted"] = True
            self._send_json(200, {"ok": True, "data": r})
            return
        if action == "moves":
            self._send_json(200, {"ok": True, "data": {
                "moves": self.car.moves_for(account)}})
            return
        self._send_json(
            400, {"ok": False, "error": "accion desconocida"}
        )
    except Exception:
        self._send_json(500, {
            "ok": False, "error": "server error",
            "trace": traceback.format_exc(),
        })


def market_gov_cartera_api(self) -> None:
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
        if action == "set_rate":
            r = self.car.set_rate(
                from_cur=str(doc.get("from_cur", "")),
                to_cur=str(doc.get("to_cur", "")),
                rate=doc.get("rate", 0),
                by=user["username"])
            self._send_json(200, {"ok": True, "data": r})
            return
        self._send_json(
            400, {"ok": False, "error": "accion desconocida"}
        )
    except Exception:
        self._send_json(500, {
            "ok": False, "error": "server error",
            "trace": traceback.format_exc(),
        })
