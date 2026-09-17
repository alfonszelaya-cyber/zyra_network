"""ZYRA MARKET - Riesgo y Proteccion (Modulo 009).

Disputas con expediente completo: apertura, evidencia,
mediacion, decision, apelacion y resolucion final.
La apelacion PRESERVA la decision (fix v3).
Reembolsos registrados como movimientos (dinero real:
motor cartera, Bloque 9). Banderas de fraude.
HTML con patron join (sin + fragiles)."""
from __future__ import annotations

import threading
import time
import uuid


def _now() -> str:
    return time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())


def _nid(prefix: str) -> str:
    return prefix + uuid.uuid4().hex[:10]


EDITABLE = ("open", "under_review", "appeal_window")


class DisputesStore:
    def __init__(self, db, clock) -> None:
        self._db = db
        self._clock = clock
        self._lock = threading.Lock()
        self._ensure_schema()

    def _ensure_schema(self) -> None:
        self._run(
            "CREATE TABLE IF NOT EXISTS sbs_disputes ("
            " dispute_id TEXT PRIMARY KEY,"
            " order_id TEXT NOT NULL,"
            " opener_account TEXT NOT NULL,"
            " role TEXT NOT NULL,"
            " reason TEXT NOT NULL,"
            " status TEXT NOT NULL,"
            " decision TEXT,"
            " refund_amount REAL,"
            " created_at TEXT NOT NULL,"
            " updated_at TEXT NOT NULL)"
        )
        self._run(
            "CREATE TABLE IF NOT EXISTS sbs_dispute_events ("
            " event_id TEXT PRIMARY KEY,"
            " dispute_id TEXT NOT NULL,"
            " actor_account TEXT NOT NULL,"
            " kind TEXT NOT NULL,"
            " content TEXT NOT NULL,"
            " created_at TEXT NOT NULL)"
        )
        self._run(
            "CREATE TABLE IF NOT EXISTS sbs_refunds ("
            " refund_id TEXT PRIMARY KEY,"
            " dispute_id TEXT,"
            " order_id TEXT NOT NULL,"
            " amount REAL NOT NULL,"
            " status TEXT NOT NULL,"
            " created_at TEXT NOT NULL)"
        )
        self._run(
            "CREATE TABLE IF NOT EXISTS sbs_fraud_flags ("
            " flag_id TEXT PRIMARY KEY,"
            " subject_account TEXT NOT NULL,"
            " reason TEXT NOT NULL,"
            " severity TEXT NOT NULL,"
            " status TEXT NOT NULL,"
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
            assembled += DisputesStore._literal(v)
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

    def _add_event(self, dispute_id, actor_account, kind, content):
        self._run(
            "INSERT INTO sbs_dispute_events (event_id, dispute_id,"
            " actor_account, kind, content, created_at)"
            " VALUES (?, ?, ?, ?, ?, ?)",
            (_nid("DVE-"), dispute_id, actor_account, kind, content, _now()),
        )

    def open_dispute(self, *, order_id, opener_account, role, reason):
        order_id = self._req(order_id, "order_id")
        opener_account = self._req(opener_account, "opener_account")
        role = self._req(role, "role")
        reason = self._req(reason, "reason")
        with self._lock:
            dispute_id = _nid("DSP-")
            now = _now()
            self._run(
                "INSERT INTO sbs_disputes (dispute_id, order_id,"
                " opener_account, role, reason, status, decision,"
                " refund_amount, created_at, updated_at)"
                " VALUES (?, ?, ?, ?, ?, 'open', NULL, NULL, ?, ?)",
                (dispute_id, order_id, opener_account, role, reason, now, now),
            )
            self._add_event(
                dispute_id, opener_account, "message",
                "apertura de disputa: %s" % reason,
            )
            return self.get_dispute(dispute_id)

    def add_event(self, dispute_id, *, actor_account, kind, content):
        dispute_id = self._req(dispute_id, "dispute_id")
        actor_account = self._req(actor_account, "actor_account")
        kind = self._req(kind, "kind")
        content = self._req(content, "content")
        if kind not in ("evidence", "message"):
            raise ValueError("kind debe ser evidence o message")
        with self._lock:
            row = self._dispute_row(dispute_id)
            if row is None:
                raise LookupError("disputa no encontrada: %s" % dispute_id)
            status = str(self._field(row, "s", 5))
            if status not in EDITABLE:
                raise ValueError(
                    "la disputa esta %s: expediente cerrado" % status
                )
            self._add_event(dispute_id, actor_account, kind, content)
        return self.get_dispute(dispute_id)

    def _dispute_row(self, dispute_id):
        rows = self._rows(
            "SELECT dispute_id, order_id, opener_account, role, reason,"
            " status, decision, refund_amount, created_at, updated_at"
            " FROM sbs_disputes WHERE dispute_id = "
            + self._literal(dispute_id)
        )
        if not rows:
            return None
        return rows[0]

    def get_dispute(self, dispute_id):
        row = self._dispute_row(self._req(dispute_id, "dispute_id"))
        if row is None:
            raise LookupError("disputa no encontrada: %s" % dispute_id)
        events = []
        for e in self._rows(
            "SELECT event_id, actor_account, kind, content, created_at"
            " FROM sbs_dispute_events WHERE dispute_id = "
            + self._literal(dispute_id)
            + " ORDER BY created_at ASC"
        ):
            events.append({
                "event_id": self._field(e, "a", 0),
                "actor_account": self._field(e, "b", 1),
                "kind": self._field(e, "c", 2),
                "content": self._field(e, "d", 3),
                "created_at": self._field(e, "e", 4),
            })
        refunds = []
        for r in self._rows(
            "SELECT refund_id, order_id, amount, status, created_at"
            " FROM sbs_refunds WHERE dispute_id = "
            + self._literal(dispute_id)
            + " ORDER BY created_at ASC"
        ):
            refunds.append({
                "refund_id": self._field(r, "a", 0),
                "order_id": self._field(r, "b", 1),
                "amount": self._field(r, "c", 2),
                "status": self._field(r, "d", 3),
                "created_at": self._field(r, "e", 4),
            })
        return {
            "dispute_id": self._field(row, "a", 0),
            "order_id": self._field(row, "b", 1),
            "opener_account": self._field(row, "c", 2),
            "role": self._field(row, "d", 3),
            "reason": self._field(row, "e", 4),
            "status": self._field(row, "f", 5),
            "decision": self._field(row, "g", 6),
            "refund_amount": self._field(row, "h", 7),
            "created_at": self._field(row, "i", 8),
            "updated_at": self._field(row, "j", 9),
            "events": events,
            "refunds": refunds,
        }

    def list_disputes(self, status=None):
        sql = (
            "SELECT dispute_id, order_id, opener_account, role, reason,"
            " status, decision, refund_amount, created_at, updated_at"
            " FROM sbs_disputes"
        )
        if status:
            sql += " WHERE status = " + self._literal(str(status))
        sql += " ORDER BY created_at DESC"
        out = []
        for row in self._rows(sql):
            out.append({
                "dispute_id": self._field(row, "a", 0),
                "order_id": self._field(row, "b", 1),
                "opener_account": self._field(row, "c", 2),
                "role": self._field(row, "d", 3),
                "reason": self._field(row, "e", 4),
                "status": self._field(row, "f", 5),
                "decision": self._field(row, "g", 6),
                "refund_amount": self._field(row, "h", 7),
                "created_at": self._field(row, "i", 8),
                "updated_at": self._field(row, "j", 9),
            })
        return out

    def _set_status(self, dispute_id, status, decision=None, refund_amount=None):
        self._run(
            "UPDATE sbs_disputes SET status = "
            + self._literal(status)
            + ", decision = "
            + self._literal(decision)
            + ", refund_amount = "
            + self._literal(refund_amount)
            + ", updated_at = "
            + self._literal(_now())
            + " WHERE dispute_id = "
            + self._literal(dispute_id)
        )

    def mediate(self, dispute_id, *, arbiter, note):
        arbiter = self._req(arbiter, "arbiter")
        note = self._req(note, "note")
        with self._lock:
            row = self._dispute_row(dispute_id)
            if row is None:
                raise LookupError("disputa no encontrada")
            status = str(self._field(row, "f", 5))
            if status not in ("open", "under_review"):
                raise ValueError(
                    "no se puede mediar en estado %s" % status
                )
            decision = self._field(row, "g", 6)
            refund_amount = self._field(row, "h", 7)
            self._set_status(
                dispute_id, "under_review", decision, refund_amount
            )
            self._add_event(
                dispute_id, arbiter, "mediation",
                "mediacion: %s" % note,
            )
        return self.get_dispute(dispute_id)

    def decide(self, dispute_id, *, arbiter, approve, note, refund_amount):
        arbiter = self._req(arbiter, "arbiter")
        note = self._req(note, "note")
        amount = float(refund_amount or 0)
        with self._lock:
            row = self._dispute_row(dispute_id)
            if row is None:
                raise LookupError("disputa no encontrada")
            status = str(self._field(row, "f", 5))
            order_id = str(self._field(row, "b", 1))
            if status not in ("open", "under_review"):
                raise ValueError(
                    "no se puede decidir en estado %s" % status
                )
            decision = "approved" if approve else "rejected"
            self._set_status(
                dispute_id, "decided", decision,
                amount if approve else None,
            )
            self._add_event(
                dispute_id, arbiter, "decision",
                "decision: %s — %s" % (decision, note),
            )
            if approve and amount > 0:
                self._run(
                    "INSERT INTO sbs_refunds (refund_id, dispute_id,"
                    " order_id, amount, status, created_at)"
                    " VALUES (?, ?, ?, ?, 'executed', ?)",
                    (_nid("RFD-"), dispute_id, order_id, amount, _now()),
                )
        return self.get_dispute(dispute_id)

    def appeal(self, dispute_id, *, appellant, reason):
        appellant = self._req(appellant, "appellant")
        reason = self._req(reason, "reason")
        with self._lock:
            row = self._dispute_row(dispute_id)
            if row is None:
                raise LookupError("disputa no encontrada")
            status = str(self._field(row, "f", 5))
            if status != "decided":
                raise ValueError(
                    "solo se apela una decision (estado %s)" % status
                )
            decision = self._field(row, "g", 6)
            refund_amount = self._field(row, "h", 7)
            self._set_status(
                dispute_id, "appeal_window", decision, refund_amount
            )
            self._add_event(
                dispute_id, appellant, "appeal",
                "apelacion: %s" % reason,
            )
        return self.get_dispute(dispute_id)

    def resolve_appeal(self, dispute_id, *, arbiter, uphold, note):
        arbiter = self._req(arbiter, "arbiter")
        note = self._req(note, "note")
        with self._lock:
            row = self._dispute_row(dispute_id)
            if row is None:
                raise LookupError("disputa no encontrada")
            status = str(self._field(row, "f", 5))
            decision = str(self._field(row, "g", 6) or "")
            if status != "appeal_window":
                raise ValueError(
                    "sin apelacion abierta (estado %s)" % status
                )
            if uphold:
                self._set_status(dispute_id, "final", decision)
                self._add_event(
                    dispute_id, arbiter, "decision",
                    "apelacion resuelta: se mantiene %s — %s"
                    % (decision, note),
                )
            else:
                self._set_status(dispute_id, "final", "overturned")
                self._reverse_refund(dispute_id)
                self._add_event(
                    dispute_id, arbiter, "decision",
                    "apelacion resuelta: decision revertida — %s" % note,
                )
        return self.get_dispute(dispute_id)

    def _reverse_refund(self, dispute_id):
        self._run(
            "UPDATE sbs_refunds SET status = 'reversed'"
            " WHERE dispute_id = " + self._literal(dispute_id)
        )

    def flag_fraud(self, *, subject_account, reason, severity):
        subject_account = self._req(subject_account, "subject_account")
        reason = self._req(reason, "reason")
        severity = str(severity or "media").strip() or "media"
        if severity not in ("baja", "media", "alta"):
            raise ValueError("severity debe ser baja, media o alta")
        with self._lock:
            flag_id = _nid("FRD-")
            self._run(
                "INSERT INTO sbs_fraud_flags (flag_id, subject_account,"
                " reason, severity, status, created_at)"
                " VALUES (?, ?, ?, ?, 'open', ?)",
                (flag_id, subject_account, reason, severity, _now()),
            )
            return {
                "flag_id": flag_id,
                "subject_account": subject_account,
                "severity": severity,
                "status": "open",
            }

    def list_fraud(self):
        out = []
        for row in self._rows(
            "SELECT flag_id, subject_account, reason, severity,"
            " status, created_at FROM sbs_fraud_flags"
            " ORDER BY created_at DESC"
        ):
            out.append({
                "flag_id": self._field(row, "a", 0),
                "subject_account": self._field(row, "b", 1),
                "reason": self._field(row, "c", 2),
                "severity": self._field(row, "d", 3),
                "status": self._field(row, "e", 4),
                "created_at": self._field(row, "f", 5),
            })
        return out


def market_disputes_page(self) -> str:
    rows = self.disputes.list_disputes()
    cards = []
    for d in rows:
        cards.append("".join([
            "<div class='card'>",
            "<p><b>%s</b> — %s</p>" % (d["dispute_id"], d["status"]),
            "<p>Orden: %s | Abrio: %s (%s)</p>" % (
                d["order_id"], d["opener_account"], d["role"]),
            "<p>%s</p>" % d["reason"],
            "<p><a href='/subastas/disputa/%s'>Abrir expediente</a></p>" % d["dispute_id"],
            "</div>",
        ]))
    if not cards:
        cards.append("<p>No hay disputas registradas.</p>")
    body = "".join([
        "<div class='card'><h2>Riesgo y Proteccion — DISPUTAS</h2>",
        "<p>Proteccion del comprador y del vendedor. El gobierno media y decide.</p>",
        "<h3>Abrir disputa</h3>",
        "<input id='dOrder' placeholder='ID de orden (ORD-...)'>",
        "<input id='dWho' placeholder='Tu cuenta'>",
        "<select id='dRole'>",
        "<option value='comprador'>comprador</option>",
        "<option value='vendedor'>vendedor</option>",
        "</select>",
        "<input id='dWhy' placeholder='Motivo'>",
        "<button id='btnOpen'>Abrir disputa</button>",
        "</div>",
        "".join(cards),
        "<p id='msg'></p>",
        "<script>",
        "document.getElementById('btnOpen').addEventListener('click',function(){",
        "function g(i){return document.getElementById(i).value;}",
        "fetch('/subastas/api/disputes',{method:'POST',",
        "headers:{'Content-Type':'application/json'},",
        "body:JSON.stringify({order_id:g('dOrder'),opener_account:g('dWho'),role:g('dRole'),reason:g('dWhy')})})",
        ".then(function(r){return r.json();})",
        ".then(function(d){if(d.ok){location.reload();}",
        "else{document.getElementById('msg').textContent='Error: '+(d.error||'');}})",
        ".catch(function(e){document.getElementById('msg').textContent='Error: '+e;});});",
        "</script>",
    ])
    return self._page_wrap("ZYRA MARKET - Proteccion", body)


def market_fraud_page(self) -> str:
    flags = self.disputes.list_fraud()
    rows = []
    for f in flags:
        rows.append("".join([
            "<div class='card'>",
            "<p><b>%s</b> — %s (%s)</p>" % (
                f["subject_account"], f["severity"], f["status"]),
            "<p>%s</p>" % f["reason"],
            "</div>",
        ]))
    if not rows:
        rows.append("<p>Sin banderas de fraude.</p>")
    body = "".join([
        "<div class='card'><h2>Riesgo y Proteccion — FRAUDE</h2>",
        "<p>Banderas de fraude (gobierno). La investigacion profunda llega con el Bloque 8.</p>",
        "<input id='fWho' placeholder='Cuenta sospechosa'>",
        "<input id='fWhy' placeholder='Motivo'>",
        "<select id='fSev'>",
        "<option value='baja'>baja</option>",
        "<option value='media'>media</option>",
        "<option value='alta'>alta</option>",
        "</select>",
        "<button id='btnFlag'>Marcar fraude</button>",
        "</div>",
        "".join(rows),
        "<p id='msg'></p>",
        "<script>",
        "document.getElementById('btnFlag').addEventListener('click',function(){",
        "function g(i){return document.getElementById(i).value;}",
        "fetch('/subastas/api/fraud',{method:'POST',",
        "headers:{'Content-Type':'application/json'},",
        "body:JSON.stringify({subject_account:g('fWho'),reason:g('fWhy'),severity:g('fSev')})})",
        ".then(function(r){return r.json();})",
        ".then(function(d){if(d.ok){location.reload();}",
        "else{document.getElementById('msg').textContent='Error: '+(d.error||'');}})",
        ".catch(function(e){document.getElementById('msg').textContent='Error: '+e;});});",
        "</script>",
    ])
    return self._page_wrap("ZYRA MARKET - Fraude", body)


def market_dispute_detail(self, dispute_id: str) -> str:
    try:
        d = self.disputes.get_dispute(dispute_id)
    except Exception:
        d = None
    if not d:
        body = "<p>No existe la disputa: <code>%s</code></p>" % dispute_id
        return self._page_wrap("Disputa no encontrada", body)
    ev = []
    for e in d["events"]:
        ev.append(
            "<p><b>[%s] %s (%s):</b> %s</p>"
            % (e["created_at"], e["actor_account"], e["kind"], e["content"])
        )
    rf = []
    for r in d["refunds"]:
        rf.append(
            "<p>Reembolso %s: $%s (%s)</p>"
            % (r["refund_id"], format(float(r["amount"] or 0), ".2f"), r["status"])
        )
    if not rf:
        rf.append("<p>Sin reembolsos registrados.</p>")
    body = "".join([
        "<div class='card'><h2>Disputa %s</h2>" % d["dispute_id"],
        "<p>Estado: <b>%s</b> | Decision: %s</p>" % (d["status"], str(d.get("decision"))),
        "<p>Orden: %s | Abrio: %s (%s)</p>" % (
            d["order_id"], d["opener_account"], d["role"]),
        "<p>Motivo: %s</p>" % d["reason"],
        "<h3>Expediente</h3>",
        "".join(ev),
        "</div>",
        "<div class='card'><h2>Reembolsos</h2>",
        "".join(rf),
        "</div>",
        "<div class='card'><h2>Acciones</h2>",
        "<p><b>Evidencia / mensaje</b> (comprador o vendedor)</p>",
        "<input id='evActor' placeholder='Tu cuenta'>",
        "<select id='evKind'>",
        "<option value='evidence'>evidencia</option>",
        "<option value='message'>mensaje</option>",
        "</select>",
        "<input id='evContent' placeholder='Contenido'>",
        "<button id='btnEv'>Agregar</button>",
        "<p><b>Mediar</b> (gobierno)</p>",
        "<input id='mdArb' placeholder='Cuenta del arbitro'>",
        "<input id='mdNote' placeholder='Nota de mediacion'>",
        "<button id='btnMd'>Mediar</button>",
        "<p><b>Decidir</b> (gobierno)</p>",
        "<input id='dcArb' placeholder='Cuenta del arbitro'>",
        "<select id='dcOk'>",
        "<option value='true'>A favor de quien abrio</option>",
        "<option value='false'>En contra</option>",
        "</select>",
        "<input id='dcNote' placeholder='Nota de decision'>",
        "<input id='dcRef' type='number' step='0.01' placeholder='Monto reembolso (si aplica)'>",
        "<button id='btnDc'>Decidir</button>",
        "<p><b>Apelar</b> (tras decision)</p>",
        "<input id='apWho' placeholder='Tu cuenta'>",
        "<input id='apWhy' placeholder='Motivo de apelacion'>",
        "<button id='btnAp'>Apelar</button>",
        "<p><b>Resolucion final</b> (gobierno, tras apelacion)</p>",
        "<input id='fnArb' placeholder='Cuenta del arbitro'>",
        "<select id='fnUp'>",
        "<option value='true'>Mantener decision</option>",
        "<option value='false'>Revertir decision</option>",
        "</select>",
        "<input id='fnNote' placeholder='Nota final'>",
        "<button id='btnFn'>Cerrar definitivo</button>",
        "<p id='msg'></p>",
        "</div>",
        "<script>",
        "function v(id){return document.getElementById(id).value;}",
        "function post(path,payload){",
        "fetch(path,{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify(payload)})",
        ".then(function(r){return r.json();})",
        ".then(function(d){if(d.ok){location.reload();}",
        "else{document.getElementById('msg').textContent='Error: '+(d.error||'');}})",
        ".catch(function(e){document.getElementById('msg').textContent='Error: '+e;});}",
        "var base='/subastas/api/disputes/%s/';" % d["dispute_id"],
        "document.getElementById('btnEv').addEventListener('click',function(){",
        "post(base+'event',{actor:v('evActor'),kind:v('evKind'),content:v('evContent')});});",
        "document.getElementById('btnMd').addEventListener('click',function(){",
        "post(base+'mediate',{arbiter:v('mdArb'),note:v('mdNote')});});",
        "document.getElementById('btnDc').addEventListener('click',function(){",
        "post(base+'decide',{arbiter:v('dcArb'),approve:v('dcOk')==='true',note:v('dcNote'),refund_amount:parseFloat(v('dcRef'))||0});});",
        "document.getElementById('btnAp').addEventListener('click',function(){",
        "post(base+'appeal',{appellant:v('apWho'),reason:v('apWhy')});});",
        "document.getElementById('btnFn').addEventListener('click',function(){",
        "post(base+'final',{arbiter:v('fnArb'),uphold:v('fnUp')==='true',note:v('fnNote')});});",
        "</script>",
    ])
    return self._page_wrap("ZYRA MARKET - Disputa", body)


def market_dispute_open(self) -> None:
    doc = self._read_json()
    if doc is None:
        self._send_json(400, {"ok": False, "error": "invalid JSON"})
        return
    dispute = self.disputes.open_dispute(
        order_id=str(doc.get("order_id", "")),
        opener_account=str(doc.get("opener_account", "")),
        role=str(doc.get("role", "")),
        reason=str(doc.get("reason", "")),
    )
    self._send_json(201, {"ok": True, "data": dispute})


def market_dispute_action(self, dispute_id: str, action: str) -> None:
    doc = self._read_json() or {}
    if action == "event":
        self.disputes.add_event(
            dispute_id,
            actor_account=str(doc.get("actor", "")),
            kind=str(doc.get("kind", "message")),
            content=str(doc.get("content", "")),
        )
    elif action == "mediate":
        self.disputes.mediate(
            dispute_id,
            arbiter=str(doc.get("arbiter", "")),
            note=str(doc.get("note", "")),
        )
    elif action == "decide":
        self.disputes.decide(
            dispute_id,
            arbiter=str(doc.get("arbiter", "")),
            approve=bool(doc.get("approve", False)),
            note=str(doc.get("note", "")),
            refund_amount=float(doc.get("refund_amount", 0) or 0),
        )
    elif action == "appeal":
        self.disputes.appeal(
            dispute_id,
            appellant=str(doc.get("appellant", "")),
            reason=str(doc.get("reason", "")),
        )
    elif action == "final":
        self.disputes.resolve_appeal(
            dispute_id,
            arbiter=str(doc.get("arbiter", "")),
            uphold=bool(doc.get("uphold", True)),
            note=str(doc.get("note", "")),
        )
    else:
        self._send_json(
            400,
            {"ok": False, "error": "unknown dispute action: %s" % action},
        )
        return
    self._send_json(
        200, {"ok": True, "data": self.disputes.get_dispute(dispute_id)}
    )


def market_fraud_flag(self) -> None:
    doc = self._read_json()
    if doc is None:
        self._send_json(400, {"ok": False, "error": "invalid JSON"})
        return
    flag = self.disputes.flag_fraud(
        subject_account=str(doc.get("subject_account", "")),
        reason=str(doc.get("reason", "")),
        severity=str(doc.get("severity", "media")),
    )
    self._send_json(201, {"ok": True, "data": flag})
