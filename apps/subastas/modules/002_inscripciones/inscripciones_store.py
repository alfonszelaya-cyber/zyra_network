"""ZYRA MARKET - Inscripciones y Usuarios (Modulo 002).

Cuentas usuario+contrasena (hash con salt por usuario,
nunca texto plano) vinculadas al ZID biometrico.
Perfil de inscripcion completo. KYB de empresas con
verificacion de gobierno. Sesiones por token con
expiracion. Roles: comprador, vendedor, gobierno, admin.
HTML con patron join (sin + fragiles)."""
from __future__ import annotations

import hashlib
import secrets
import threading
import time
import uuid


def _now() -> str:
    return time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())


def _ts() -> float:
    return time.time()


def _nid(prefix: str) -> str:
    return prefix + uuid.uuid4().hex[:10]


SESSION_TTL_SECONDS = 7 * 24 * 3600


class AccountsStore:
    def __init__(self, db, clock) -> None:
        self._db = db
        self._clock = clock
        self._lock = threading.Lock()
        self._ensure_schema()

    def _ensure_schema(self) -> None:
        self._run(
            "CREATE TABLE IF NOT EXISTS sbs_users ("
            " user_id TEXT PRIMARY KEY,"
            " username TEXT UNIQUE NOT NULL,"
            " pass_hash TEXT NOT NULL,"
            " salt TEXT NOT NULL,"
            " zid TEXT,"
            " role TEXT NOT NULL,"
            " display_name TEXT NOT NULL,"
            " status TEXT NOT NULL,"
            " created_at TEXT NOT NULL,"
            " updated_at TEXT NOT NULL)"
        )
        self._run(
            "CREATE TABLE IF NOT EXISTS sbs_profiles ("
            " user_id TEXT PRIMARY KEY,"
            " address TEXT,"
            " phone TEXT,"
            " category TEXT,"
            " payout_info TEXT,"
            " updated_at TEXT NOT NULL)"
        )
        self._run(
            "CREATE TABLE IF NOT EXISTS sbs_companies ("
            " company_id TEXT PRIMARY KEY,"
            " name TEXT NOT NULL,"
            " rep_user_id TEXT NOT NULL,"
            " rep_name TEXT NOT NULL,"
            " rep_doc TEXT NOT NULL,"
            " doc_ref TEXT,"
            " status TEXT NOT NULL,"
            " created_at TEXT NOT NULL,"
            " updated_at TEXT NOT NULL)"
        )
        self._run(
            "CREATE TABLE IF NOT EXISTS sbs_sessions ("
            " token TEXT PRIMARY KEY,"
            " user_id TEXT NOT NULL,"
            " created_at REAL NOT NULL,"
            " expires_at REAL NOT NULL)"
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
            assembled += AccountsStore._literal(v)
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

    @staticmethod
    def _hash_password(password, salt):
        return hashlib.sha256(
            (salt + ":" + str(password)).encode("utf-8")
        ).hexdigest()

    @staticmethod
    def _valid_role(role):
        role = str(role or "comprador").strip() or "comprador"
        if role not in ("comprador", "vendedor", "gobierno", "admin"):
            raise ValueError("role invalido: %s" % role)
        return role

    def register_user(self, *, username, password, display_name, zid=None, role="comprador"):
        username = self._req(username, "username").lower()
        password = self._req(password, "password")
        display_name = self._req(display_name, "display_name")
        role = self._valid_role(role)
        if len(password) < 6:
            raise ValueError("la contrasena debe tener al menos 6 caracteres")
        with self._lock:
            existing = self._rows(
                "SELECT user_id FROM sbs_users WHERE username = "
                + self._literal(username)
            )
            if existing:
                raise ValueError("el usuario ya existe: %s" % username)
            user_id = _nid("USR-")
            salt = secrets.token_hex(16)
            pass_hash = self._hash_password(password, salt)
            now = _now()
            self._run(
                "INSERT INTO sbs_users (user_id, username, pass_hash,"
                " salt, zid, role, display_name, status,"
                " created_at, updated_at)"
                " VALUES (?, ?, ?, ?, ?, ?, ?, 'active', ?, ?)",
                (
                    user_id, username, pass_hash, salt,
                    zid if (isinstance(zid, str) and zid.startswith("ZID-")) else None,
                    role, display_name, now, now,
                ),
            )
            self._run(
                "INSERT INTO sbs_profiles (user_id, address, phone,"
                " category, payout_info, updated_at)"
                " VALUES (?, NULL, NULL, NULL, NULL, ?)",
                (user_id, now),
            )
            return self.get_user(username)

    def get_user(self, username):
        username = self._req(username, "username").lower()
        rows = self._rows(
            "SELECT user_id, username, pass_hash, salt, zid, role,"
            " display_name, status, created_at, updated_at"
            " FROM sbs_users WHERE username = "
            + self._literal(username)
        )
        if not rows:
            return None
        row = rows[0]
        return {
            "user_id": self._field(row, "a", 0),
            "username": self._field(row, "b", 1),
            "zid": self._field(row, "d", 4),
            "role": self._field(row, "e", 5),
            "display_name": self._field(row, "f", 6),
            "status": self._field(row, "g", 7),
        }

    def verify_login(self, username, password):
        username = self._req(username, "username").lower()
        password = self._req(password, "password")
        rows = self._rows(
            "SELECT user_id, username, pass_hash, salt, zid, role,"
            " display_name, status FROM sbs_users WHERE username = "
            + self._literal(username)
        )
        if not rows:
            raise ValueError("usuario o contrasena incorrectos")
        row = rows[0]
        status = str(self._field(row, "h", 7))
        if status != "active":
            raise ValueError("cuenta no activa: %s" % status)
        stored = str(self._field(row, "c", 2))
        salt = str(self._field(row, "d", 3))
        if self._hash_password(password, salt) != stored:
            raise ValueError("usuario o contrasena incorrectos")
        return {
            "user_id": self._field(row, "a", 0),
            "username": self._field(row, "b", 1),
            "zid": self._field(row, "e", 4),
            "role": self._field(row, "f", 5),
            "display_name": self._field(row, "g", 6),
        }

    def set_role(self, username, role):
        role = self._valid_role(role)
        username = self._req(username, "username").lower()
        with self._lock:
            self._run(
                "UPDATE sbs_users SET role = "
                + self._literal(role)
                + ", updated_at = "
                + self._literal(_now())
                + " WHERE username = "
                + self._literal(username)
            )
        return self.get_user(username)

    def link_zid(self, username, zid):
        username = self._req(username, "username").lower()
        zid = self._req(zid, "zid")
        if not zid.startswith("ZID-"):
            raise ValueError("zid invalido")
        with self._lock:
            self._run(
                "UPDATE sbs_users SET zid = "
                + self._literal(zid)
                + ", updated_at = "
                + self._literal(_now())
                + " WHERE username = "
                + self._literal(username)
            )
        return self.get_user(username)

    def update_profile(self, username, *, address=None, phone=None, category=None, payout_info=None):
        username = self._req(username, "username").lower()
        user = self.get_user(username)
        if user is None:
            raise LookupError("usuario no encontrado")
        user_id = user["user_id"]
        with self._lock:
            fields = []
            values = []
            if address is not None:
                fields.append("address")
                values.append(str(address))
            if phone is not None:
                fields.append("phone")
                values.append(str(phone))
            if category is not None:
                fields.append("category")
                values.append(str(category))
            if payout_info is not None:
                fields.append("payout_info")
                values.append(str(payout_info))
            if not fields:
                raise ValueError("nada que actualizar")
            sets = []
            for f in fields:
                sets.append(f + " = " + self._literal(values.pop(0)))
            sets.append("updated_at = " + self._literal(_now()))
            self._run(
                "UPDATE sbs_profiles SET "
                + ", ".join(sets)
                + " WHERE user_id = "
                + self._literal(user_id)
            )
        return self.get_profile(username)

    def get_profile(self, username):
        username = self._req(username, "username").lower()
        user = self.get_user(username)
        if user is None:
            raise LookupError("usuario no encontrado")
        rows = self._rows(
            "SELECT address, phone, category, payout_info, updated_at"
            " FROM sbs_profiles WHERE user_id = "
            + self._literal(user["user_id"])
        )
        prof = {
            "address": None, "phone": None,
            "category": None, "payout_info": None,
            "updated_at": None,
        }
        if rows:
            row = rows[0]
            prof = {
                "address": self._field(row, "a", 0),
                "phone": self._field(row, "b", 1),
                "category": self._field(row, "c", 2),
                "payout_info": self._field(row, "d", 3),
                "updated_at": self._field(row, "e", 4),
            }
        return {"user": user, "profile": prof}

    def register_company(self, *, name, rep_username, rep_name, rep_doc, doc_ref=None):
        name = self._req(name, "name")
        rep_username = self._req(rep_username, "rep_username").lower()
        rep_name = self._req(rep_name, "rep_name")
        rep_doc = self._req(rep_doc, "rep_doc")
        user = self.get_user(rep_username)
        if user is None:
            raise LookupError("representante no existe: %s" % rep_username)
        with self._lock:
            company_id = _nid("CMP-")
            now = _now()
            self._run(
                "INSERT INTO sbs_companies (company_id, name,"
                " rep_user_id, rep_name, rep_doc, doc_ref, status,"
                " created_at, updated_at)"
                " VALUES (?, ?, ?, ?, ?, ?, 'pending', ?, ?)",
                (
                    company_id, name, user["user_id"],
                    rep_name, rep_doc,
                    str(doc_ref) if doc_ref else None,
                    now, now,
                ),
            )
            return self.get_company(company_id)

    def get_company(self, company_id):
        company_id = self._req(company_id, "company_id")
        rows = self._rows(
            "SELECT company_id, name, rep_user_id, rep_name, rep_doc,"
            " doc_ref, status, created_at, updated_at"
            " FROM sbs_companies WHERE company_id = "
            + self._literal(company_id)
        )
        if not rows:
            return None
        row = rows[0]
        return {
            "company_id": self._field(row, "a", 0),
            "name": self._field(row, "b", 1),
            "rep_user_id": self._field(row, "c", 2),
            "rep_name": self._field(row, "d", 3),
            "rep_doc": self._field(row, "e", 4),
            "doc_ref": self._field(row, "f", 5),
            "status": self._field(row, "g", 6),
        }

    def list_companies(self, status=None):
        sql = (
            "SELECT company_id, name, rep_user_id, rep_name, rep_doc,"
            " doc_ref, status, created_at, updated_at FROM sbs_companies"
        )
        if status:
            sql += " WHERE status = " + self._literal(str(status))
        sql += " ORDER BY created_at DESC"
        out = []
        for row in self._rows(sql):
            out.append({
                "company_id": self._field(row, "a", 0),
                "name": self._field(row, "b", 1),
                "rep_name": self._field(row, "d", 3),
                "doc_ref": self._field(row, "f", 5),
                "status": self._field(row, "g", 6),
            })
        return out

    def verify_company(self, company_id, *, approve):
        company_id = self._req(company_id, "company_id")
        with self._lock:
            status = "verified" if approve else "rejected"
            self._run(
                "UPDATE sbs_companies SET status = "
                + self._literal(status)
                + ", updated_at = "
                + self._literal(_now())
                + " WHERE company_id = "
                + self._literal(company_id)
            )
        return self.get_company(company_id)

    def create_session(self, username):
        username = self._req(username, "username").lower()
        user = self.get_user(username)
        if user is None:
            raise LookupError("usuario no encontrado")
        token = secrets.token_urlsafe(32)
        now = _ts()
        with self._lock:
            self._run(
                "INSERT INTO sbs_sessions (token, user_id,"
                " created_at, expires_at) VALUES (?, ?, ?, ?)",
                (token, user["user_id"], now, now + SESSION_TTL_SECONDS),
            )
        return token

    def _user_by_id(self, user_id):
        rows = self._rows(
            "SELECT user_id, username, zid, role, display_name, status"
            " FROM sbs_users WHERE user_id = "
            + self._literal(user_id)
        )
        if not rows:
            return None
        row = rows[0]
        return {
            "user_id": self._field(row, "a", 0),
            "username": self._field(row, "b", 1),
            "zid": self._field(row, "c", 2),
            "role": self._field(row, "d", 3),
            "display_name": self._field(row, "e", 4),
            "status": self._field(row, "f", 5),
        }

    def session_user(self, token):
        if not token or not str(token).strip():
            return None
        rows = self._rows(
            "SELECT user_id, created_at, expires_at FROM sbs_sessions"
            " WHERE token = " + self._literal(str(token))
        )
        if not rows:
            return None
        row = rows[0]
        expires = float(self._field(row, "c", 2) or 0)
        if _ts() > expires:
            self.destroy_session(str(token))
            return None
        return self._user_by_id(str(self._field(row, "a", 0)))

    def destroy_session(self, token):
        with self._lock:
            self._run(
                "DELETE FROM sbs_sessions WHERE token = "
                + self._literal(str(token or ""))
            )
        return True

    def cleanup_sessions(self):
        with self._lock:
            self._run(
                "DELETE FROM sbs_sessions WHERE expires_at < " + repr(_ts())
            )
        return True


def _sess_user(self):
    cookie = self.headers.get("Cookie", "") or ""
    token = None
    for part in cookie.split(";"):
        if "=" in part:
            k, v = part.split("=", 1)
            if k.strip() == "zyra_sess":
                token = v.strip()
                break
    if not token:
        return None
    return self.accounts.session_user(token)


def _require_role(self, user, *roles):
    if user is None:
        raise PermissionError("sesion requerida: entra a Inscripcion")
    if roles and user.get("role") not in roles:
        raise PermissionError(
            "tu rol (%s) no permite esta accion" % user.get("role")
        )


def market_inscripcion_page(self) -> str:
    user = self._sess_user()
    head = []
    if user:
        head.append("".join([
            "<div class='card'><h2>Sesion activa</h2>",
            "<p>Hola <b>%s</b> — rol: <b>%s</b></p>" % (
                user["display_name"], user["role"]),
            "<p>ZID: %s</p>" % (user["zid"] or "pendiente (haz el registro biometrico)"),
            "<form method='POST' action='/subastas/logout'>",
            "<button>Cerrar sesion</button></form>",
            "</div>",
        ]))
    else:
        head.append("".join([
            "<div class='card'><h2>Entrar</h2>",
            "<form method='POST' action='/subastas/login'>",
            "<input name='username' placeholder='Usuario' required>",
            "<input name='password' type='password' placeholder='Contrasena' required>",
            "<button>Entrar</button>",
            "</form></div>",
        ]))
    prof = []
    if user:
        try:
            p = self.accounts.get_profile(user["username"])
            pr = p["profile"]
        except Exception:
            pr = {}
        prof.append("".join([
            "<div class='card'><h2>Mi perfil de inscripcion</h2>",
            "<p>Direccion: %s</p>" % (pr.get("address") or "-"),
            "<p>Telefono: %s</p>" % (pr.get("phone") or "-"),
            "<p>Categoria comercial: %s</p>" % (pr.get("category") or "-"),
            "<p>Datos de cobro: %s</p>" % (pr.get("payout_info") or "-"),
            "<h3>Actualizar perfil</h3>",
            "<form method='POST' action='/subastas/perfil'>",
            "<input name='address' placeholder='Direccion'>",
            "<input name='phone' placeholder='Telefono'>",
            "<input name='category' placeholder='Categoria (ej. electronica)'>",
            "<input name='payout_info' placeholder='Datos de cobro'>",
            "<button>Guardar perfil</button>",
            "</form></div>",
            "<div class='card'><h2>Registrar mi empresa (KYB)</h2>",
            "<p>El gobierno verifica la empresa. Necesitas sesion de vendedor.</p>",
            "<form method='POST' action='/subastas/empresa'>",
            "<input name='company_name' placeholder='Nombre de la empresa' required>",
            "<input name='rep_name' placeholder='Nombre del representante' required>",
            "<input name='rep_doc' placeholder='Documento del representante' required>",
            "<input name='doc_ref' placeholder='Referencia de documentos'>",
            "<button>Registrar empresa</button>",
            "</form></div>",
            "<div class='card'><h2>Vincular mi ZID</h2>",
            "<p>Si ya hiciste el registro biometrico, pega tu ZID aqui.</p>",
            "<form method='POST' action='/subastas/vincular'>",
            "<input name='zid' placeholder='ZID-...'>",
            "<button>Vincular ZID</button>",
            "</form></div>",
        ]))
    reg = "".join([
        "<div class='card'><h2>Crear cuenta</h2>",
        "<p>La identidad la da el registro biometrico (por ley);",
        " la contrasena es para entrar comodamente.</p>",
        "<form method='POST' action='/subastas/registro'>",
        "<input name='username' placeholder='Usuario (sin espacios)' required>",
        "<input name='password' type='password' placeholder='Contrasena (min 6)' required>",
        "<input name='display_name' placeholder='Tu nombre' required>",
        "<select name='role'>",
        "<option value='comprador'>comprador</option>",
        "<option value='vendedor'>vendedor</option>",
        "</select>",
        "<button>Crear cuenta</button>",
        "</form></div>",
    ])
    body = "".join(head + prof + [reg])
    return self._page_wrap("ZYRA MARKET - Inscripcion", body)


def market_login(self) -> None:
    form = self._read_form()
    user = self.accounts.verify_login(
        self._form_value(form, "username"),
        self._form_value(form, "password"),
    )
    token = self.accounts.create_session(user["username"])
    self.send_response(303)
    self.send_header("Location", "/subastas/inscripcion")
    self.send_header(
        "Set-Cookie",
        "zyra_sess=%s; Path=/; Max-Age=%s; HttpOnly"
        % (token, SESSION_TTL_SECONDS),
    )
    self.end_headers()


def market_logout(self) -> None:
    cookie = self.headers.get("Cookie", "") or ""
    for part in cookie.split(";"):
        if "=" in part:
            k, v = part.split("=", 1)
            if k.strip() == "zyra_sess":
                self.accounts.destroy_session(v.strip())
    self.send_response(303)
    self.send_header("Location", "/subastas/inscripcion")
    self.send_header("Set-Cookie", "zyra_sess=; Path=/; Max-Age=0")
    self.end_headers()


def market_register_user(self) -> None:
    form = self._read_form()
    user = self.accounts.register_user(
        username=self._form_value(form, "username"),
        password=self._form_value(form, "password"),
        display_name=self._form_value(form, "display_name"),
        role=self._form_value(form, "role") or "comprador",
    )
    token = self.accounts.create_session(user["username"])
    self.send_response(303)
    self.send_header("Location", "/subastas/inscripcion")
    self.send_header(
        "Set-Cookie",
        "zyra_sess=%s; Path=/; Max-Age=%s; HttpOnly"
        % (token, SESSION_TTL_SECONDS),
    )
    self.end_headers()


def market_update_profile(self) -> None:
    user = self._sess_user()
    self._require_role(user, "comprador", "vendedor", "gobierno", "admin")
    form = self._read_form()
    self.accounts.update_profile(
        user["username"],
        address=self._form_value(form, "address") or None,
        phone=self._form_value(form, "phone") or None,
        category=self._form_value(form, "category") or None,
        payout_info=self._form_value(form, "payout_info") or None,
    )
    self._send_html(200, "".join([
        "<html><body><h1>ZYRA MARKET</h1>",
        "<p>Perfil actualizado.</p>",
        "<p><a href='/subastas/inscripcion'><button>Volver</button></a></p>",
        "</body></html>",
    ]))


def market_link_zid(self) -> None:
    user = self._sess_user()
    self._require_role(user, "comprador", "vendedor", "gobierno", "admin")
    form = self._read_form()
    updated = self.accounts.link_zid(
        user["username"], self._form_value(form, "zid")
    )
    self._send_html(200, "".join([
        "<html><body><h1>ZYRA MARKET</h1>",
        "<p>ZID vinculado: %s</p>" % updated["zid"],
        "<p><a href='/subastas/inscripcion'><button>Volver</button></a></p>",
        "</body></html>",
    ]))


def market_register_company(self) -> None:
    user = self._sess_user()
    self._require_role(user, "vendedor", "gobierno", "admin")
    form = self._read_form()
    company = self.accounts.register_company(
        name=self._form_value(form, "company_name"),
        rep_username=user["username"],
        rep_name=self._form_value(form, "rep_name"),
        rep_doc=self._form_value(form, "rep_doc"),
        doc_ref=self._form_value(form, "doc_ref") or None,
    )
    self._send_html(200, "".join([
        "<html><body><h1>ZYRA MARKET</h1>",
        "<p>Empresa registrada: %s (%s)</p>" % (
            company["name"], company["company_id"]),
        "<p>Estado: %s — pendiente de verificacion del gobierno.</p>" % company["status"],
        "<p><a href='/subastas/inscripcion'><button>Volver</button></a></p>",
        "</body></html>",
    ]))


def market_gobierno_page(self) -> str:
    user = self._sess_user()
    self._require_role(user, "gobierno", "admin")
    companies = self.accounts.list_companies()
    rows = []
    for c in companies:
        rows.append("".join([
            "<div class='card'>",
            "<p><b>%s</b> — %s</p>" % (c["name"], c["status"]),
            "<p>ID: <code>%s</code> | Rep: %s</p>" % (
                c["company_id"], c["rep_name"]),
            "</div>",
        ]))
    if not rows:
        rows.append("<p>Sin empresas registradas.</p>")
    body = "".join([
        "<div class='card'><h2>Verificacion de empresas (KYB)</h2>",
        "<input id='kybId' placeholder='ID de empresa (CMP-...)'>",
        "<select id='kybOk'>",
        "<option value='true'>Verificar (aprobar)</option>",
        "<option value='false'>Rechazar</option>",
        "</select>",
        "<button id='btnKyb'>Aplicar verificacion</button>",
        "</div>",
        "".join(rows),
        "<p id='msg'></p>",
        "<script>",
        "document.getElementById('btnKyb').addEventListener('click',function(){",
        "function g(i){return document.getElementById(i).value;}",
        "fetch('/subastas/api/empresa/verificar',{method:'POST',",
        "headers:{'Content-Type':'application/json'},",
        "body:JSON.stringify({company_id:g('kybId'),approve:g('kybOk')==='true'})})",
        ".then(function(r){return r.json();})",
        ".then(function(d){if(d.ok){location.reload();}",
        "else{document.getElementById('msg').textContent='Error: '+(d.error||'');}})",
        ".catch(function(e){document.getElementById('msg').textContent='Error: '+e;});});",
        "</script>",
    ])
    return self._page_wrap("ZYRA MARKET - Gobierno KYB", body)


def market_verify_company(self) -> None:
    user = self._sess_user()
    self._require_role(user, "gobierno", "admin")
    doc = self._read_json()
    if doc is None:
        self._send_json(400, {"ok": False, "error": "invalid JSON"})
        return
    company = self.accounts.verify_company(
        str(doc.get("company_id", "")),
        approve=bool(doc.get("approve", False)),
    )
    self._send_json(200, {"ok": True, "data": company})
