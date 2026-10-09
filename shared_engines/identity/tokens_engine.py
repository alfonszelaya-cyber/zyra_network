"""Identity Tokens Engine (ID-11) - access+refresh con
scopes, expiracion, reuso detectado, revoke_all.
Reglas 63/66/76."""
from __future__ import annotations
import hashlib, json, secrets, uuid
from shared_engines.common.clocks import Clock
from shared_engines.storage.database import Database
from shared_engines.storage.migrations import (
    Migration, MigrationRunner)

_MIGRATIONS = (
    Migration(1, "zid_tokens", (
        "CREATE TABLE IF NOT EXISTS zid_tokens ("
        " token_id TEXT PRIMARY KEY, zid TEXT NOT"
        " NULL, kind TEXT NOT NULL, token_hash TEXT"
        " NOT NULL, scopes_json TEXT NOT NULL DEFAULT"
        " '[]', expires_at REAL NOT NULL, used INTEGER"
        " NOT NULL DEFAULT 0, revoked INTEGER NOT"
        " NULL DEFAULT 0, created_at REAL NOT NULL)",
    )),
)
_KINDS = ("access", "refresh")


def _sha(t):
    return hashlib.sha256(
        t.encode("utf-8")).hexdigest()


class TokensEngine:
    """Tokens con refresh (ID-11)."""

    def __init__(self, db: Database, clock: Clock):
        self._db = db
        self._clock = clock
        MigrationRunner(db, "zid.tokens",
                        _MIGRATIONS).run(clock)

    def issue_pair(self, *, zid, scopes=None,
                   access_ttl=3600.0,
                   refresh_ttl=604800.0):
        if not str(zid).strip():
            raise ValueError("zid requerido")
        sc = [str(s) for s in (scopes or [])]
        now = self._clock.now()
        access = "ZAT-" + secrets.token_urlsafe(24)
        refresh = "ZRT-" + secrets.token_urlsafe(24)
        self._db.execute(
            "INSERT INTO zid_tokens (token_id, zid,"
            " kind, token_hash, scopes_json,"
            " expires_at, created_at)"
            " VALUES (?, ?, 'access', ?, ?, ?, ?)",
            ("ZTK-" + uuid.uuid4().hex[:10],
             str(zid), _sha(access),
             json.dumps(sc),
             now + float(access_ttl), now))
        self._db.execute(
            "INSERT INTO zid_tokens (token_id, zid,"
            " kind, token_hash, scopes_json,"
            " expires_at, created_at)"
            " VALUES (?, ?, 'refresh', ?, ?, ?, ?)",
            ("ZTK-" + uuid.uuid4().hex[:10],
             str(zid), _sha(refresh),
             json.dumps(sc),
             now + float(refresh_ttl), now))
        return {"access_token": access,
                "refresh_token": refresh,
                "expires_in": int(access_ttl)}

    def check_access(self, token):
        row = self._db.query_one(
            "SELECT zid, scopes_json, expires_at,"
            " revoked FROM zid_tokens WHERE"
            " token_hash = ? AND kind = 'access'",
            (_sha(str(token)),))
        if row is None:
            return {"valid": False,
                    "reason": "desconocido"}
        if int(row["revoked"]) == 1:
            return {"valid": False,
                    "reason": "revocado"}
        if float(row["expires_at"]) <= \
                self._clock.now():
            return {"valid": False,
                    "reason": "expirado"}
        return {"valid": True,
                "zid": str(row["zid"]),
                "scopes": json.loads(
                    str(row["scopes_json"]))}

    def refresh(self, refresh_token, *,
                access_ttl=3600.0):
        row = self._db.query_one(
            "SELECT zid, scopes_json, expires_at,"
            " used, revoked FROM zid_tokens WHERE"
            " token_hash = ? AND kind = 'refresh'",
            (_sha(str(refresh_token)),))
        if row is None:
            raise LookupError("no existe")
        if int(row["used"]) == 1:
            raise ValueError(
                "refresh ya usado (reuso)")
        if int(row["revoked"]) == 1:
            raise ValueError("revocado")
        if float(row["expires_at"]) <= \
                self._clock.now():
            raise ValueError("expirado")
        self._db.execute(
            "UPDATE zid_tokens SET used = 1 WHERE"
            " token_hash = ?",
            (_sha(str(refresh_token)),))
        sc = json.loads(str(row["scopes_json"]))
        access = "ZAT-" + secrets.token_urlsafe(24)
        self._db.execute(
            "INSERT INTO zid_tokens (token_id, zid,"
            " kind, token_hash, scopes_json,"
            " expires_at, created_at)"
            " VALUES (?, ?, 'access', ?, ?, ?, ?)",
            ("ZTK-" + uuid.uuid4().hex[:10],
             str(row["zid"]), _sha(access),
             json.dumps(sc),
             self._clock.now()
             + float(access_ttl),
             self._clock.now()))
        return {"access_token": access,
                "expires_in": int(access_ttl)}

    def revoke_all(self, zid):
        n = self._db.query_one(
            "SELECT COUNT(*) AS n FROM zid_tokens"
            " WHERE zid = ? AND revoked = 0",
            (str(zid),))
        self._db.execute(
            "UPDATE zid_tokens SET revoked = 1 WHERE"
            " zid = ? AND revoked = 0",
            (str(zid),))
        return {"zid": str(zid),
                "revoked": int(n["n"])}
