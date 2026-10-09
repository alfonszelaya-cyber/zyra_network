"""OIDC Bridge Engine (ID-10) - scopes OIDC estandar,
tokens con expiracion, introspeccion, revocacion.
Reglas 63/66/76."""
from __future__ import annotations
import hashlib, json, secrets, uuid
from shared_engines.common.clocks import Clock
from shared_engines.storage.database import Database
from shared_engines.storage.migrations import (
    Migration, MigrationRunner)

_MIGRATIONS = (
    Migration(1, "zid_oidc_tokens", (
        "CREATE TABLE IF NOT EXISTS zid_oidc_tokens ("
        " token_id TEXT PRIMARY KEY, zid TEXT NOT"
        " NULL, client_id TEXT NOT NULL, token_hash"
        " TEXT NOT NULL, scopes_json TEXT NOT NULL"
        " DEFAULT '[]', expires_at REAL NOT NULL,"
        " revoked INTEGER NOT NULL DEFAULT 0,"
        " created_at REAL NOT NULL)",
    )),
)
_SCOPES = ("openid", "profile", "email", "agro",
           "semilla", "nexo")


def _sha(t):
    return hashlib.sha256(
        t.encode("utf-8")).hexdigest()


class OidcBridgeEngine:
    """Puente OIDC sobre ZID (ID-10)."""

    def __init__(self, db: Database, clock: Clock):
        self._db = db
        self._clock = clock
        MigrationRunner(db, "zid.oidc",
                        _MIGRATIONS).run(clock)

    def issue_token(self, *, zid, client_id,
                    scopes, ttl_seconds=3600.0):
        if not str(zid).strip() or \
                not str(client_id).strip():
            raise ValueError(
                "zid y client_id requeridos")
        sc = [str(s).lower()
              for s in (scopes or [])]
        if not sc:
            raise ValueError(
                "scopes requeridos (regla 66)")
        for s in sc:
            if s not in _SCOPES:
                raise ValueError(
                    "scope invalido: " + s
                    + " (validos: "
                    + "/".join(_SCOPES) + ")")
        token = "ZT-" + secrets.token_urlsafe(24)
        tid = "ZOT-" + uuid.uuid4().hex[:10]
        exp = self._clock.now() + float(ttl_seconds)
        self._db.execute(
            "INSERT INTO zid_oidc_tokens (token_id,"
            " zid, client_id, token_hash, scopes_json,"
            " expires_at, revoked, created_at)"
            " VALUES (?, ?, ?, ?, ?, ?, 0, ?)",
            (tid, str(zid), str(client_id),
             _sha(token), json.dumps(sc), exp,
             self._clock.now()))
        return {"token": token,
                "expires_in": int(ttl_seconds),
                "scopes": sc}

    def introspect(self, token):
        row = self._db.query_one(
            "SELECT zid, client_id, scopes_json,"
            " expires_at, revoked FROM"
            " zid_oidc_tokens WHERE token_hash = ?",
            (_sha(str(token)),))
        if row is None:
            return {"active": False,
                    "reason": "desconocido"}
        if int(row["revoked"]) == 1:
            return {"active": False,
                    "reason": "revocado"}
        if float(row["expires_at"]) <= \
                self._clock.now():
            return {"active": False,
                    "reason": "expirado"}
        return {"active": True,
                "zid": str(row["zid"]),
                "client_id": str(
                    row["client_id"]),
                "scopes": json.loads(
                    str(row["scopes_json"]))}

    def revoke_token(self, token):
        row = self._db.query_one(
            "SELECT revoked FROM zid_oidc_tokens"
            " WHERE token_hash = ?",
            (_sha(str(token)),))
        if row is None:
            raise LookupError("no existe")
        if int(row["revoked"]) == 1:
            raise ValueError("ya revocado")
        self._db.execute(
            "UPDATE zid_oidc_tokens SET revoked = 1"
            " WHERE token_hash = ?",
            (_sha(str(token)),))
        return {"revoked": True}
