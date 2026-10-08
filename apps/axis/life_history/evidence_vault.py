
"""AXIS Evidence Vault (AX-9): integridad sha256 +
custodia con transiciones validadas (presentada
SOLO liberacion; liberada TERMINAL). Patron
_DDL + ensure_db."""
from __future__ import annotations
import base64
import hashlib
import uuid
from shared_engines.storage.database import (
    Database)

_DDL = (
    "CREATE TABLE IF NOT EXISTS ax_ev_items ("
    " ev_id TEXT PRIMARY KEY, ref_kind TEXT NOT"
    " NULL, ref_id TEXT NOT NULL, kind TEXT NOT"
    " NULL, description TEXT NOT NULL, sha256"
    " TEXT NOT NULL, status TEXT NOT NULL DEFAULT"
    " 'ingresada', created_at TEXT NOT NULL"
    " DEFAULT '')",
    "CREATE TABLE IF NOT EXISTS ax_ev_custody ("
    " cust_id TEXT PRIMARY KEY, ev_id TEXT NOT"
    " NULL, actor TEXT NOT NULL, action TEXT NOT"
    " NULL, note TEXT NOT NULL DEFAULT '', at"
    " TEXT NOT NULL DEFAULT '')",
)
_REF = ("JUSTICIA", "POLICIA", "FORENSE")
_KINDS = ("FISICA", "DIGITAL", "BIOLOGICA",
          "DOCUMENTAL", "MULTIMEDIA")
_ALLOWED = {
    "ingresada": ("TRANSFERENCIA", "ANALISIS",
                  "PRESENTACION",
                  "LIBERACION"),
    "en_custodia": ("TRANSFERENCIA", "ANALISIS",
                    "PRESENTACION",
                    "LIBERACION"),
    "analizada": ("PRESENTACION", "LIBERACION",
                  "TRANSFERENCIA"),
    "presentada": ("LIBERACION",),
    "liberada": (),
}
_ACTION_STATUS = {"TRANSFERENCIA": "en_custodia",
                  "ANALISIS": "analizada",
                  "PRESENTACION": "presentada",
                  "LIBERACION": "liberada"}


def ensure_db(db):
    for stmt in _DDL:
        db.execute(stmt)


def ingest_db(db, *, ref_kind, ref_id, kind,
              description, content_b64="",
              sha256_hex="", actor="",
              at=""):
    ensure_db(db)
    rk = str(ref_kind).upper()
    if rk not in _REF:
        raise ValueError("ref_kind debe ser "
                         + "/".join(_REF))
    k = str(kind).upper()
    if k not in _KINDS:
        raise ValueError("kind debe ser "
                         + "/".join(_KINDS))
    if not str(description).strip():
        raise ValueError(
            "description requerida")
    if str(content_b64).strip():
        digest = hashlib.sha256(
            base64.b64decode(
                str(content_b64))
            ).hexdigest()
    elif str(sha256_hex).strip():
        digest = (str(sha256_hex).strip()
                  .lower())
        if len(digest) != 64:
            raise ValueError(
                "sha256 64 hex")
    else:
        raise ValueError(
            "content_b64 o sha256_hex"
            " requerido")
    eid = ("AXEV-"
           + uuid.uuid4().hex[:10])
    db.execute(
        "INSERT INTO ax_ev_items (ev_id,"
        " ref_kind, ref_id, kind, description,"
        " sha256, status, created_at)"
        " VALUES (?, ?, ?, ?, ?, ?, 'ingresada',"
        " ?)",
        (eid, rk, str(ref_id), k,
         str(description), digest,
         str(at)))
    db.execute(
        "INSERT INTO ax_ev_custody (cust_id,"
        " ev_id, actor, action, note, at)"
        " VALUES (?, ?, ?, 'INGRESO',"
        " 'ingreso con integridad', ?)",
        ("AXCU-" + uuid.uuid4().hex[:10],
         eid, str(actor), str(at)))
    return {"ev_id": eid, "sha256": digest,
            "status": "ingresada"}


def _item(db, ev_id):
    row = db.query_one(
        "SELECT ev_id, status FROM ax_ev_items"
        " WHERE ev_id = ?", (str(ev_id),))
    if row is None:
        raise LookupError(
            "evidencia no encontrada: "
            + str(ev_id))
    return row


def _do_action(db, ev_id, *, action, actor,
               note="", at=""):
    row = _item(db, ev_id)
    cur = str(row["status"])
    a = str(action).upper()
    if a not in _ALLOWED.get(cur, ()):
        raise ValueError(
            "transicion invalida: " + cur
            + " -> " + a)
    if not str(actor).strip():
        raise ValueError(
            "actor requerido")
    db.execute(
        "INSERT INTO ax_ev_custody (cust_id,"
        " ev_id, actor, action, note, at)"
        " VALUES (?, ?, ?, ?, ?, ?)",
        ("AXCU-" + uuid.uuid4().hex[:10],
         str(ev_id), str(actor), a,
         str(note), str(at)))
    new = _ACTION_STATUS[a]
    db.execute(
        "UPDATE ax_ev_items SET status = ?"
        " WHERE ev_id = ?",
        (new, str(ev_id)))
    return {"ev_id": str(ev_id),
            "action": a, "status": new}


def transfer_db(db, ev_id, *, actor,
                to_location="", at=""):
    ensure_db(db)
    return _do_action(
        db, ev_id, action="TRANSFERENCIA",
        actor=actor,
        note="a " + str(to_location),
        at=at)


def analyze_db(db, ev_id, *, actor, note="",
               at=""):
    ensure_db(db)
    return _do_action(db, ev_id,
                      action="ANALISIS",
                      actor=actor,
                      note=note, at=at)


def present_db(db, ev_id, *, actor, at=""):
    ensure_db(db)
    return _do_action(db, ev_id,
                      action="PRESENTACION",
                      actor=actor, at=at)


def release_db(db, ev_id, *, actor, at=""):
    ensure_db(db)
    return _do_action(db, ev_id,
                      action="LIBERACION",
                      actor=actor, at=at)


def custody_of_db(db, ev_id):
    ensure_db(db)
    rows = db.query_all(
        "SELECT cust_id, actor, action, note, at"
        " FROM ax_ev_custody WHERE ev_id = ?"
        " ORDER BY rowid", (str(ev_id),))
    return [{"cust_id": str(r["cust_id"]),
             "actor": str(r["actor"]),
             "action": str(r["action"]),
             "note": str(r["note"]),
             "at": str(r["at"])}
            for r in rows]


def custody_verified_db(db, ev_id):
    ensure_db(db)
    rows = db.query_all(
        "SELECT action FROM ax_ev_custody WHERE"
        " ev_id = ? ORDER BY rowid",
        (str(ev_id),))
    if not rows:
        return False
    if str(rows[0]["action"]) != "INGRESO":
        return False
    prev = "ingresada"
    for r in rows[1:]:
        a = str(r["action"])
        if a not in _ALLOWED.get(prev, ()):
            return False
        prev = _ACTION_STATUS[a]
    return True
