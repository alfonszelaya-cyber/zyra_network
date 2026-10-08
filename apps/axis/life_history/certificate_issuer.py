
"""AX-18b Certificate Issuer: certificados con
hash-chain por titular, verificacion publica,
revocacion CON motivo. Patron _DDL + ensure_db."""
from __future__ import annotations
import hashlib
import uuid
from shared_engines.storage.database import (
    Database)

_DDL = (
    "CREATE TABLE IF NOT EXISTS ax_certs ("
    " cert_id TEXT PRIMARY KEY, cert_code TEXT NOT"
    " NULL UNIQUE, person_id TEXT NOT NULL, zid"
    " TEXT NOT NULL DEFAULT '', kind TEXT NOT"
    " NULL, payload TEXT NOT NULL DEFAULT '',"
    " status TEXT NOT NULL DEFAULT 'VIGENTE',"
    " revoked_reason TEXT NOT NULL DEFAULT '',"
    " prev_hash TEXT NOT NULL DEFAULT '',"
    " entry_hash TEXT NOT NULL, created_at TEXT"
    " NOT NULL DEFAULT '')",
)
_KINDS = ("CIVIL", "MEDICO", "JUDICIAL",
          "POLICIAL", "MIGRATORIO")


def ensure_db(db):
    for stmt in _DDL:
        db.execute(stmt)


def _sha(text):
    return hashlib.sha256(
        text.encode("utf-8")).hexdigest()


def issue_db(db, *, person_id, kind, payload="",
             zid="", at=""):
    ensure_db(db)
    if not str(person_id).strip():
        raise ValueError(
            "person_id requerido")
    k = str(kind).upper()
    if k not in _KINDS:
        raise ValueError("kind invalido")
    if not str(payload).strip():
        raise ValueError("payload requerido")
    row = db.query_one(
        "SELECT entry_hash FROM ax_certs WHERE"
        " person_id = ? ORDER BY rowid DESC"
        " LIMIT 1", (str(person_id),))
    prev = (str(row["entry_hash"])
            if row else "")
    eh = _sha(prev + "|" + str(person_id) + "|"
              + k + "|" + str(payload) + "|"
              + str(at))
    cid = ("AXCT-"
           + uuid.uuid4().hex[:10])
    code = ("CERT-" + cid[4:])
    db.execute(
        "INSERT INTO ax_certs (cert_id, cert_code,"
        " person_id, zid, kind, payload, status,"
        " revoked_reason, prev_hash, entry_hash,"
        " created_at) VALUES (?, ?, ?, ?, ?, ?,"
        " 'VIGENTE', '', ?, ?, ?)",
        (cid, code, str(person_id), str(zid), k,
         str(payload), prev, eh, str(at)))
    return {"cert_id": cid, "cert_code": code,
            "entry_hash": eh}


def verify_db(db, cert_code):
    ensure_db(db)
    row = db.query_one(
        "SELECT kind, status, revoked_reason FROM"
        " ax_certs WHERE cert_code = ?",
        (str(cert_code),))
    if row is None:
        return {"found": False}
    return {"found": True,
            "kind": str(row["kind"]),
            "status": str(row["status"]),
            "revoked_reason": str(
                row["revoked_reason"])}


def revoke_cert_db(db, cert_code, *, reason,
                   at=""):
    ensure_db(db)
    row = db.query_one(
        "SELECT status FROM ax_certs WHERE"
        " cert_code = ?", (str(cert_code),))
    if row is None:
        raise KeyError(cert_code)
    if str(row["status"]) != "VIGENTE":
        raise ValueError("ya revocado")
    if not str(reason).strip():
        raise ValueError("motivo obligatorio")
    db.execute(
        "UPDATE ax_certs SET status ="
        " 'REVOCADO', revoked_reason = ? WHERE"
        " cert_code = ?",
        (str(reason), str(cert_code)))
    return {"cert_code": str(cert_code),
            "status": "REVOCADO"}


def certs_of_db(db, person_id):
    ensure_db(db)
    rows = db.query_all(
        "SELECT cert_code, kind, status FROM"
        " ax_certs WHERE person_id = ? ORDER BY"
        " rowid", (str(person_id),))
    return [{"cert_code": str(r["cert_code"]),
             "kind": str(r["kind"]),
             "status": str(r["status"])}
            for r in rows]
