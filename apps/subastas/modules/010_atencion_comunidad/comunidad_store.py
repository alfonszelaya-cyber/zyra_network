"""ZYRA MARKET - Modulo Comunidad (completo).

Feed, perfil publico, seguidores, comentarios, reacciones,
chat 1-a-1, preguntas en publicaciones, notificaciones,
reportes y moderacion. Patron join."""
from __future__ import annotations

import threading
import time
import uuid


def _now() -> str:
    return time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())


def _nid(prefix: str) -> str:
    return prefix + uuid.uuid4().hex[:10]


class ComunidadStore:
    def __init__(self, db, clock) -> None:
        self._db = db
        self._clock = clock
        self._lock = threading.Lock()
        self._ensure_schema()

    def _ensure_schema(self) -> None:
        self._run(
            "CREATE TABLE IF NOT EXISTS sbs_posts ("
            " post_id TEXT PRIMARY KEY,"
            " author TEXT NOT NULL,"
            " content TEXT NOT NULL,"
            " hidden INTEGER NOT NULL DEFAULT 0,"
            " created_at TEXT NOT NULL)"
        )
        self._run(
            "CREATE TABLE IF NOT EXISTS sbs_comments ("
            " com_id TEXT PRIMARY KEY,"
            " post_id TEXT NOT NULL,"
            " author TEXT NOT NULL,"
            " content TEXT NOT NULL,"
            " hidden INTEGER NOT NULL DEFAULT 0,"
            " created_at TEXT NOT NULL)"
        )
        self._run(
            "CREATE TABLE IF NOT EXISTS sbs_reactions ("
            " rea_id TEXT PRIMARY KEY,"
            " post_id TEXT NOT NULL,"
            " account TEXT NOT NULL,"
            " kind TEXT NOT NULL,"
            " created_at TEXT NOT NULL)"
        )
        self._run(
            "CREATE TABLE IF NOT EXISTS sbs_follows ("
            " fol_id TEXT PRIMARY KEY,"
            " follower TEXT NOT NULL,"
            " followed TEXT NOT NULL,"
            " created_at TEXT NOT NULL)"
        )
        self._run(
            "CREATE TABLE IF NOT EXISTS sbs_messages ("
            " msg_id TEXT PRIMARY KEY,"
            " from_a TEXT NOT NULL,"
            " to_a TEXT NOT NULL,"
            " content TEXT NOT NULL,"
            " created_at TEXT NOT NULL)"
        )
        self._run(
            "CREATE TABLE IF NOT EXISTS sbs_notifications ("
            " not_id TEXT PRIMARY KEY,"
            " account TEXT NOT NULL,"
            " kind TEXT NOT NULL,"
            " detail TEXT NOT NULL,"
            " read_flag INTEGER NOT NULL DEFAULT 0,"
            " created_at TEXT NOT NULL)"
        )
        self._run(
            "CREATE TABLE IF NOT EXISTS sbs_reports ("
            " rep_id TEXT PRIMARY KEY,"
            " reporter TEXT NOT NULL,"
            " target_kind TEXT NOT NULL,"
            " target_id TEXT NOT NULL,"
            " reason TEXT NOT NULL,"
            " status TEXT NOT NULL,"
            " created_at TEXT NOT NULL,"
            " resolved_at TEXT)"
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
            assembled += ComunidadStore._literal(v)
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

    def _notify(self, account, kind, detail):
        self._run(
            "INSERT INTO sbs_notifications (not_id, account, kind,"
            " detail, read_flag, created_at) VALUES (?, ?, ?, ?, 0, ?)",
            (_nid("NOT-"), account, kind, detail, _now()),
        )

    def _count(self, sql):
        rows = self._rows(sql)
        if not rows:
            return 0
        row = rows[0]
        if isinstance(row, dict):
            for v in row.values():
                return int(v or 0)
            return 0
        try:
            return int(row[0] or 0)
        except Exception:
            return 0

    def create_post(self, *, author, content):
        author = self._req(author, "author")
        content = self._req(content, "content")
        with self._lock:
            post_id = _nid("PST-")
            self._run(
                "INSERT INTO sbs_posts (post_id, author, content,"
                " hidden, created_at) VALUES (?, ?, ?, 0, ?)",
                (post_id, author, content, _now()),
            )
            return {"post_id": post_id, "author": author,
                    "content": content}

    def feed(self, limit=30):
        out = []
        for row in self._rows(
            "SELECT post_id, author, content, created_at"
            " FROM sbs_posts WHERE hidden = 0"
            " ORDER BY created_at DESC LIMIT " + str(int(limit))
        ):
            pid = str(self._field(row, "a", 0))
            out.append({
                "post_id": pid,
                "author": self._field(row, "b", 1),
                "content": self._field(row, "c", 2),
                "created_at": self._field(row, "d", 3),
                "likes": self._count(
                    "SELECT COUNT(*) FROM sbs_reactions WHERE post_id = "
                    + self._literal(pid) + " AND kind = 'like'"),
                "hearts": self._count(
                    "SELECT COUNT(*) FROM sbs_reactions WHERE post_id = "
                    + self._literal(pid) + " AND kind = 'heart'"),
                "comments": self._count(
                    "SELECT COUNT(*) FROM sbs_comments WHERE post_id = "
                    + self._literal(pid) + " AND hidden = 0"),
            })
        return out

    def comment(self, *, post_id, author, content):
        post_id = self._req(post_id, "post_id")
        author = self._req(author, "author")
        content = self._req(content, "content")
        with self._lock:
            prow = self._rows(
                "SELECT author, hidden FROM sbs_posts WHERE post_id = "
                + self._literal(post_id)
            )
            if not prow:
                raise LookupError("post no encontrado")
            if int(self._field(prow[0], "b", 1) or 0) == 1:
                raise ValueError("post oculto por moderacion")
            com_id = _nid("CMT-")
            self._run(
                "INSERT INTO sbs_comments (com_id, post_id, author,"
                " content, hidden, created_at) VALUES (?, ?, ?, ?, 0, ?)",
                (com_id, post_id, author, content, _now()),
            )
            post_author = str(self._field(prow[0], "a", 0))
            if post_author != author:
                self._notify(
                    post_author, "comentario",
                    "%s comento tu post %s" % (author, post_id),
                )
            return {"com_id": com_id, "post_id": post_id,
                    "author": author, "content": content}

    def react(self, *, post_id, account, kind):
        post_id = self._req(post_id, "post_id")
        account = self._req(account, "account")
        if kind not in ("like", "heart"):
            raise ValueError("kind debe ser like o heart")
        with self._lock:
            dup = self._rows(
                "SELECT rea_id FROM sbs_reactions WHERE post_id = "
                + self._literal(post_id)
                + " AND account = " + self._literal(account)
                + " AND kind = " + self._literal(kind)
            )
            if dup:
                raise ValueError("ya reaccionaste con %s" % kind)
            self._run(
                "INSERT INTO sbs_reactions (rea_id, post_id, account,"
                " kind, created_at) VALUES (?, ?, ?, ?, ?)",
                (_nid("REA-"), post_id, account, kind, _now()),
            )
            prow = self._rows(
                "SELECT author FROM sbs_posts WHERE post_id = "
                + self._literal(post_id)
            )
            if prow:
                post_author = str(self._field(prow[0], "a", 0))
                if post_author != account:
                    self._notify(
                        post_author, "reaccion",
                        "%s reacciono (%s) a tu post %s"
                        % (account, kind, post_id),
                    )
            return {"post_id": post_id, "kind": kind}

    def follow(self, *, follower, followed):
        follower = self._req(follower, "follower")
        followed = self._req(followed, "followed")
        if follower == followed:
            raise ValueError("no puedes seguirte a ti mismo")
        with self._lock:
            dup = self._rows(
                "SELECT fol_id FROM sbs_follows WHERE follower = "
                + self._literal(follower)
                + " AND followed = " + self._literal(followed)
            )
            if dup:
                raise ValueError("ya lo sigues")
            self._run(
                "INSERT INTO sbs_follows (fol_id, follower, followed,"
                " created_at) VALUES (?, ?, ?, ?)",
                (_nid("FOL-"), follower, followed, _now()),
            )
            self._notify(
                followed, "seguidor",
                "%s ahora te sigue" % follower,
            )
            return {"follower": follower, "followed": followed}

    def unfollow(self, *, follower, followed):
        follower = self._req(follower, "follower")
        followed = self._req(followed, "followed")
        with self._lock:
            self._run(
                "DELETE FROM sbs_follows WHERE follower = "
                + self._literal(follower)
                + " AND followed = " + self._literal(followed)
            )
            return {"unfollowed": followed}

    def followers_count(self, account):
        return self._count(
            "SELECT COUNT(*) FROM sbs_follows WHERE followed = "
            + self._literal(str(account or "").strip())
        )

    def following_count(self, account):
        return self._count(
            "SELECT COUNT(*) FROM sbs_follows WHERE follower = "
            + self._literal(str(account or "").strip())
        )

    def send_message(self, *, from_a, to_a, content):
        from_a = self._req(from_a, "from_a")
        to_a = self._req(to_a, "to_a")
        content = self._req(content, "content")
        with self._lock:
            msg_id = _nid("MSG-")
            self._run(
                "INSERT INTO sbs_messages (msg_id, from_a, to_a,"
                " content, created_at) VALUES (?, ?, ?, ?, ?)",
                (msg_id, from_a, to_a, content, _now()),
            )
            self._notify(
                to_a, "mensaje",
                "mensaje de %s" % from_a,
            )
            return {"msg_id": msg_id, "from_a": from_a,
                    "to_a": to_a, "content": content}

    def conversation(self, a, b):
        a = self._req(a, "a")
        b = self._req(b, "b")
        out = []
        for row in self._rows(
            "SELECT msg_id, from_a, to_a, content, created_at"
            " FROM sbs_messages WHERE"
            " (from_a = " + self._literal(a)
            + " AND to_a = " + self._literal(b) + ")"
            + " OR (from_a = " + self._literal(b)
            + " AND to_a = " + self._literal(a) + ")"
            + " ORDER BY created_at ASC LIMIT 100"
        ):
            out.append({
                "msg_id": self._field(row, "a", 0),
                "from": self._field(row, "b", 1),
                "to": self._field(row, "c", 2),
                "content": self._field(row, "d", 3),
                "created_at": self._field(row, "e", 4),
            })
        return out

    def notifications_for(self, account):
        account = self._req(account, "account")
        out = []
        for row in self._rows(
            "SELECT not_id, kind, detail, read_flag, created_at"
            " FROM sbs_notifications WHERE account = "
            + self._literal(account)
            + " ORDER BY created_at DESC LIMIT 30"
        ):
            out.append({
                "not_id": self._field(row, "a", 0),
                "kind": self._field(row, "b", 1),
                "detail": self._field(row, "c", 2),
                "read": bool(self._field(row, "d", 3)),
            })
        return out

    def mark_notifications_read(self, account):
        account = self._req(account, "account")
        with self._lock:
            self._run(
                "UPDATE sbs_notifications SET read_flag = 1"
                " WHERE account = " + self._literal(account)
            )
            return True

    def report(self, *, reporter, target_kind, target_id, reason):
        reporter = self._req(reporter, "reporter")
        target_kind = str(target_kind or "").strip()
        if target_kind not in ("post", "comment", "user"):
            raise ValueError("target_kind debe ser post, comment o user")
        target_id = self._req(target_id, "target_id")
        reason = self._req(reason, "reason")
        with self._lock:
            rep_id = _nid("RPT-")
            self._run(
                "INSERT INTO sbs_reports (rep_id, reporter,"
                " target_kind, target_id, reason, status,"
                " created_at, resolved_at)"
                " VALUES (?, ?, ?, ?, ?, 'open', ?, NULL)",
                (rep_id, reporter, target_kind, target_id,
                 reason, _now()),
            )
            return {"rep_id": rep_id, "target_kind": target_kind,
                    "status": "open"}

    def list_reports(self, status="open"):
        out = []
        sql = (
            "SELECT rep_id, reporter, target_kind, target_id,"
            " reason, status, created_at FROM sbs_reports"
        )
        if status:
            sql += " WHERE status = " + self._literal(str(status))
        sql += " ORDER BY created_at DESC"
        for row in self._rows(sql):
            out.append({
                "rep_id": self._field(row, "a", 0),
                "reporter": self._field(row, "b", 1),
                "target_kind": self._field(row, "c", 2),
                "target_id": self._field(row, "d", 3),
                "reason": self._field(row, "e", 4),
                "status": self._field(row, "f", 5),
            })
        return out

    def resolve_report(self, rep_id, *, hide=False):
        rep_id = self._req(rep_id, "rep_id")
        with self._lock:
            row = self._rows(
                "SELECT target_kind, target_id FROM sbs_reports"
                " WHERE rep_id = " + self._literal(rep_id)
            )
            if not row:
                raise LookupError("reporte no encontrado")
            tkind = str(self._field(row[0], "a", 0))
            tid = str(self._field(row[0], "b", 1))
            if hide:
                if tkind == "post":
                    self._run(
                        "UPDATE sbs_posts SET hidden = 1"
                        " WHERE post_id = " + self._literal(tid)
                    )
                elif tkind == "comment":
                    self._run(
                        "UPDATE sbs_comments SET hidden = 1"
                        " WHERE com_id = " + self._literal(tid)
                    )
            self._run(
                "UPDATE sbs_reports SET status = 'resolved',"
                " resolved_at = " + self._literal(_now())
                + " WHERE rep_id = " + self._literal(rep_id)
            )
            return {"rep_id": rep_id, "resolved": True,
                    "hidden": hide}


def market_comunidad_page(self) -> str:
    user = self._sess_user()
    if user is None:
        body = "".join([
            "<div class='card'><h2>Comunidad</h2>",
            "<p>Necesitas sesion.</p>",
            "<p><a href='/subastas/inscripcion'><button>Entrar</button></a></p>",
            "</div>",
        ])
        return self._page_wrap("ZYRA MARKET - Comunidad", body)
    account = user["username"]
    feed = self.com.feed()
    nots = self.com.notifications_for(account)
    fol_n = self.com.followers_count(account)
    fol_g = self.com.following_count(account)
    f_rows = []
    for p in feed:
        f_rows.append("".join([
            "<div class='card'>",
            "<p><b>%s</b> — %s</p>" % (p["author"], p["created_at"]),
            "<p>%s</p>" % p["content"],
            "<p>likes %s | hearts %s | comentarios %s</p>" % (
                str(p["likes"]), str(p["hearts"]), str(p["comments"])),
            "<p><code>%s</code></p>" % p["post_id"],
            "</div>",
        ]))
    if not f_rows:
        f_rows.append("<div class='card'><p>Feed vacio. Publica el primero.</p></div>")
    n_rows = []
    for n in nots:
        read = "" if n["read"] else " (nueva)"
        n_rows.append("<p>- %s%s: %s</p>" % (n["kind"], read, n["detail"]))
    if not n_rows:
        n_rows.append("<p>Sin notificaciones.</p>")
    body = "".join([
        "<div class='card'><h2>Hola %s</h2>" % account,
        "<p>Seguidores: %s | Siguiendo: %s</p>" % (str(fol_n), str(fol_g)),
        "</div>",
        "<div class='card'><h2>Publicar en el feed</h2>",
        "<textarea id='fTxt' rows='2' placeholder='Que estas vendiendo?'></textarea>",
        "<button id='btnPost'>Publicar</button>",
        "</div>",
        "<div class='card'><h2>Notificaciones</h2>",
        "<button id='btnRead'>Marcar todas leidas</button>",
        "".join(n_rows),
        "</div>",
        "<div class='card'><h2>Seguir a alguien</h2>",
        "<input id='fWho' placeholder='Cuenta a seguir'>",
        "<button id='btnFollow'>Seguir</button>",
        "<input id='uWho' placeholder='Cuenta a dejar de seguir'>",
        "<button id='btnUn'>Dejar de seguir</button>",
        "</div>",
        "<div class='card'><h2>Mensajes</h2>",
        "<input id='mTo' placeholder='Cuenta destino'>",
        "<input id='mTxt' placeholder='Mensaje'>",
        "<button id='btnMsg'>Enviar</button>",
        "</div>",
        "<div class='card'><h2>Feed</h2>",
        "".join(f_rows),
        "</div>",
        "<div class='card'><h2>Acciones sobre un post</h2>",
        "<input id='pId' placeholder='ID de post (PST-...)'>",
        "<input id='pCmt' placeholder='Comentario'>",
        "<button id='btnCmt'>Comentar</button>",
        "<button id='btnLike'>Like</button>",
        "<button id='btnHeart'>Heart</button>",
        "<input id='pRep' placeholder='Motivo de reporte'>",
        "<button id='btnRep'>Reportar</button>",
        "</div>",
        "<p id='msg'></p>",
        "<script>",
        "function v(id){return document.getElementById(id).value;}",
        "function post(payload){",
        "fetch('/subastas/api/comunidad',{method:'POST',",
        "headers:{'Content-Type':'application/json'},",
        "body:JSON.stringify(payload)})",
        ".then(function(r){return r.json();})",
        ".then(function(d){if(d.ok){location.reload();}",
        "else{document.getElementById('msg').textContent='Error: '+(d.error||'');}})",
        ".catch(function(e){document.getElementById('msg').textContent='Error: '+e;});}",
        "document.getElementById('btnPost').addEventListener('click',function(){",
        "post({action:'post',content:v('fTxt')});});",
        "document.getElementById('btnRead').addEventListener('click',function(){",
        "post({action:'read_all'});});",
        "document.getElementById('btnFollow').addEventListener('click',function(){",
        "post({action:'follow',target:v('fWho')});});",
        "document.getElementById('btnUn').addEventListener('click',function(){",
        "post({action:'unfollow',target:v('uWho')});});",
        "document.getElementById('btnMsg').addEventListener('click',function(){",
        "post({action:'message',to:v('mTo'),content:v('mTxt')});});",
        "document.getElementById('btnCmt').addEventListener('click',function(){",
        "post({action:'comment',post_id:v('pId'),content:v('pCmt')});});",
        "document.getElementById('btnLike').addEventListener('click',function(){",
        "post({action:'react',post_id:v('pId'),kind:'like'});});",
        "document.getElementById('btnHeart').addEventListener('click',function(){",
        "post({action:'react',post_id:v('pId'),kind:'heart'});});",
        "document.getElementById('btnRep').addEventListener('click',function(){",
        "post({action:'report',target_kind:'post',target_id:v('pId'),reason:v('pRep')});});",
        "</script>",
    ])
    return self._page_wrap("ZYRA MARKET - Comunidad", body)


def market_gov_comunidad_page(self) -> str:
    user = self._sess_user()
    if user is None or user.get("role") not in ("gobierno", "admin"):
        body = "<p>Solo gobierno/admin.</p>"
        return self._page_wrap("ZYRA MARKET - Gov Comunidad", body)
    reports = self.com.list_reports("open")
    r_rows = []
    for r in reports:
        r_rows.append(
            "<p>- <b>%s</b> <code>%s</code> por %s: %s"
            " <code>%s</code></p>" % (
                r["target_kind"], r["target_id"],
                r["reporter"], r["reason"], r["rep_id"]))
    if not r_rows:
        r_rows.append("<p>Sin reportes abiertos.</p>")
    body = "".join([
        "<div class='card'><h2>Moderacion: reportes abiertos</h2>",
        "".join(r_rows),
        "<input id='rId' placeholder='ID de reporte (RPT-...)'>",
        "<button id='btnHide'>Resolver OCULTANDO contenido</button>",
        "<button id='btnKeep'>Resolver SIN ocultar</button>",
        "</div>",
        "<p id='msg'></p>",
        "<script>",
        "document.getElementById('btnHide').addEventListener('click',function(){",
        "postGov(true);});",
        "document.getElementById('btnKeep').addEventListener('click',function(){",
        "postGov(false);});",
        "function postGov(hide){",
        "function g(i){return document.getElementById(i).value;}",
        "fetch('/subastas/api/gov-comunidad',{method:'POST',",
        "headers:{'Content-Type':'application/json'},",
        "body:JSON.stringify({rep_id:g('rId'),hide:hide})})",
        ".then(function(r){return r.json();})",
        ".then(function(d){if(d.ok){location.reload();}",
        "else{document.getElementById('msg').textContent='Error: '+(d.error||'');}})",
        ".catch(function(e){document.getElementById('msg').textContent='Error: '+e;});}",
        "</script>",
    ])
    return self._page_wrap("ZYRA MARKET - Gov Comunidad", body)


def market_comunidad_api(self) -> None:
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
    if action == "post":
        p = self.com.create_post(author=account, content=str(doc.get("content", "")))
        self._send_json(201, {"ok": True, "data": p})
        return
    if action == "comment":
        c = self.com.comment(
            post_id=str(doc.get("post_id", "")),
            author=account, content=str(doc.get("content", "")))
        self._send_json(201, {"ok": True, "data": c})
        return
    if action == "react":
        r = self.com.react(
            post_id=str(doc.get("post_id", "")),
            account=account, kind=str(doc.get("kind", "like")))
        self._send_json(200, {"ok": True, "data": r})
        return
    if action == "follow":
        r = self.com.follow(follower=account, followed=str(doc.get("target", "")))
        self._send_json(200, {"ok": True, "data": r})
        return
    if action == "unfollow":
        r = self.com.unfollow(follower=account, followed=str(doc.get("target", "")))
        self._send_json(200, {"ok": True, "data": r})
        return
    if action == "message":
        m = self.com.send_message(
            from_a=account, to_a=str(doc.get("to", "")),
            content=str(doc.get("content", "")))
        self._send_json(201, {"ok": True, "data": m})
        return
    if action == "conversation":
        msgs = self.com.conversation(account, str(doc.get("with", "")))
        self._send_json(200, {"ok": True, "data": {"messages": msgs}})
        return
    if action == "read_all":
        self.com.mark_notifications_read(account)
        self._send_json(200, {"ok": True, "data": {"read": True}})
        return
    if action == "report":
        r = self.com.report(
            reporter=account,
            target_kind=str(doc.get("target_kind", "post")),
            target_id=str(doc.get("target_id", "")),
            reason=str(doc.get("reason", "")))
        self._send_json(201, {"ok": True, "data": r})
        return
    self._send_json(
        400, {"ok": False, "error": "accion desconocida: %s" % action}
    )


def market_gov_comunidad_api(self) -> None:
    user = self._sess_user()
    if user is None or user.get("role") not in ("gobierno", "admin"):
        self._send_json(403, {"ok": False, "error": "solo gobierno/admin"})
        return
    doc = self._read_json()
    if doc is None:
        self._send_json(400, {"ok": False, "error": "invalid JSON"})
        return
    res = self.com.resolve_report(
        str(doc.get("rep_id", "")),
        hide=bool(doc.get("hide", False)),
    )
    self._send_json(200, {"ok": True, "data": res})
