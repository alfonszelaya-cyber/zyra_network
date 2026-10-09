"""Trust Registry Engine (ID-6) - registro de
emisores/autoridades CONFIADAS de la Red: quien
puede firmar credenciales. Reglas 63/66/76."""
from __future__ import annotations
import json, uuid
from shared_engines.common.clocks import Clock
from shared_engines.storage.database import Database
from shared_engines.storage.migrations import (
    Migration, MigrationRunner)

_MIGRATIONS = (
    Migration(1, "zid_trust_issuers", (
        "CREATE TABLE IF NOT EXISTS"
        " zid_trust_issuers ("
        " issuer_id TEXT PRIMARY KEY,"
        " name TEXT NOT NULL,"
        " kind TEXT NOT NULL,"
        " scopes_json TEXT NOT NULL DEFAULT '[]',"
        " status TEXT NOT NULL DEFAULT 'trusted',"
        " revoked_reason TEXT NOT NULL DEFAULT '',"
        " created_at REAL NOT NULL)",
    )),
)
_KINDS = ("GOBIERNO", "HOSPITAL", "REGISTRO",
          "BANCO", "EDUCACION", "EXTERNO")


class TrustRegistryEngine:
    """Registro de emisores confiables (ID-6)."""

    def __init__(self, db: Database, clock: Clock):
        self._db = db
        self._clock = clock
        MigrationRunner(db, "zid.trustreg",
                        _MIGRATIONS).run(clock)

    def register(self, *, issuer_id, name, kind,
                 scopes=None):
        if not str(issuer_id).strip() or \
                not str(name).strip():
            raise ValueError(
                "issuer_id y name requeridos")
        k = str(kind).upper()
        if k not in _KINDS:
            raise ValueError("kind debe ser "
                             + "/".join(_KINDS))
        dup = self._db.query_one(
            "SELECT issuer_id FROM"
            " zid_trust_issuers WHERE issuer_id = ?",
            (str(issuer_id),))
        if dup is not None:
            raise ValueError(
                "emisor ya registrado (regla 66)")
        self._db.execute(
            "INSERT INTO zid_trust_issuers (issuer_id,"
            " name, kind, scopes_json, status,"
            " created_at) VALUES (?, ?, ?, ?,"
            " 'trusted', ?)",
            (str(issuer_id), str(name), k,
             json.dumps(list(scopes or [])),
             self._clock.now()))
        return {"issuer_id": str(issuer_id),
                "status": "trusted"}

    def is_trusted(self, issuer_id, scope=None):
        row = self._db.query_one(
            "SELECT status, scopes_json FROM"
            " zid_trust_issuers WHERE issuer_id = ?",
            (str(issuer_id),))
        if row is None:
            return False
        if str(row["status"]) != "trusted":
            return False
        if scope:
            scopes = json.loads(str(
                row["scopes_json"] or "[]"))
            if scopes and str(scope) not in scopes:
                return False
        return True

    def revoke(self, issuer_id, *, reason):
        row = self._db.query_one(
            "SELECT status FROM zid_trust_issuers"
            " WHERE issuer_id = ?",
            (str(issuer_id),))
        if row is None:
            raise KeyError(issuer_id)
        if str(row["status"]) != "trusted":
            raise ValueError("ya revocado")
        if not str(reason).strip():
            raise ValueError("motivo obligatorio")
        self._db.execute(
            "UPDATE zid_trust_issuers SET status ="
            " 'revoked', revoked_reason = ? WHERE"
            " issuer_id = ?",
            (str(reason), str(issuer_id)))
        return {"issuer_id": str(issuer_id),
                "status": "revoked"}

    def trusted_of(self, kind=None):
        if kind:
            rows = self._db.query_all(
                "SELECT issuer_id, name, kind FROM"
                " zid_trust_issuers WHERE status ="
                " 'trusted' AND kind = ? ORDER BY"
                " rowid", (str(kind).upper(),))
        else:
            rows = self._db.query_all(
                "SELECT issuer_id, name, kind FROM"
                " zid_trust_issuers WHERE status ="
                " 'trusted' ORDER BY rowid")
        return [{"issuer_id": str(r["issuer_id"]),
                 "name": str(r["name"]),
                 "kind": str(r["kind"])}
                for r in rows]
