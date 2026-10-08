
"""AXIS Criminal Record (AX-7): expediente criminal,
condenas, ANTECEDENTES hash-chain sha256
verificable, reincidencia. Patron _DDL +
ensure_db."""
from __future__ import annotations
import hashlib
import uuid
from shared_engines.storage.database import (
    Database)

_DDL = (
    "CREATE TABLE IF NOT EXISTS ax_crim_cases ("
    " crim_id TEXT PRIMARY KEY, person_id TEXT NOT"
    " NULL, zid TEXT NOT NULL DEFAULT '',"
    " ref_case_id TEXT NOT NULL DEFAULT '',"
    " status TEXT NOT NULL DEFAULT 'abierto',"
    " created_at TEXT NOT NULL DEFAULT '')",
    "CREATE TABLE IF NOT EXISTS ax_crim_charges ("
    " charge_id TEXT PRIMARY KEY, crim_id TEXT NOT"
    " NULL, charge TEXT NOT NULL, detail TEXT NOT"
    " NULL DEFAULT '', created_at TEXT NOT NULL"
    " DEFAULT '')",
    "CREATE TABLE IF NOT EXISTS ax_crim_conv ("
    " conv_id TEXT PRIMARY KEY, crim_id TEXT NOT"
    " NULL, person_id TEXT NOT NULL, charge TEXT"
    " NOT NULL, sentence_days INTEGER NOT NULL"
    " DEFAULT 0, fine REAL NOT NULL DEFAULT 0,"
    " dictated_by TEXT NOT NULL, created_at TEXT"
    " NOT NULL DEFAULT '')",
    "CREATE TABLE IF NOT EXISTS ax_crim_registry ("
    " reg_id TEXT PRIMARY KEY, person_id TEXT NOT"
    " NULL, zid TEXT NOT NULL DEFAULT '', payload"
    " TEXT NOT NULL, prev_hash TEXT NOT NULL,"
    " entry_hash TEXT NOT NULL, created_at TEXT"
    " NOT NULL DEFAULT '')",
)


def ensure_db(db):
    for stmt in _DDL:
        db.execute(stmt)


def _sha(text):
    return hashlib.sha256(
        text.encode("utf-8")).hexdigest()


def open_criminal_case_db(db, *, person_id,
                          zid="", ref_case_id="",
                          created_at=""):
    ensure_db(db)
    if not str(person_id).strip():
        raise ValueError(
            "person_id requerido")
    cid = ("AXCR-"
           + uuid.uuid4().hex[:10])
    db.execute(
        "INSERT INTO ax_crim_cases (crim_id,"
        " person_id, zid, ref_case_id, status,"
        " created_at) VALUES (?, ?, ?, ?,"
        " 'abierto', ?)",
        (cid, str(person_id), str(zid),
         str(ref_case_id), str(created_at)))
    return {"crim_id": cid,
            "status": "abierto"}


def _case(db, crim_id):
    row = db.query_one(
        "SELECT crim_id, person_id, status, zid"
        " FROM ax_crim_cases WHERE crim_id = ?",
        (str(crim_id),))
    if row is None:
        raise LookupError(
            "expediente no encontrado: "
            + str(crim_id))
    return row


def add_charge_db(db, *, crim_id, charge,
                  detail="", created_at=""):
    ensure_db(db)
    row = _case(db, crim_id)
    if str(row["status"]) != "abierto":
        raise ValueError(
            "cargos solo en abierto")
    if not str(charge).strip():
        raise ValueError(
            "charge requerida")
    cid = ("AXCC-"
           + uuid.uuid4().hex[:10])
    db.execute(
        "INSERT INTO ax_crim_charges (charge_id,"
        " crim_id, charge, detail, created_at)"
        " VALUES (?, ?, ?, ?, ?)",
        (cid, str(crim_id), str(charge),
         str(detail), str(created_at)))
    return {"charge_id": cid,
            "charge": str(charge)}


def _prev_hash(db, person_id):
    row = db.query_one(
        "SELECT entry_hash FROM"
        " ax_crim_registry WHERE person_id = ?"
        " ORDER BY rowid DESC LIMIT 1",
        (str(person_id),))
    return (str(row["entry_hash"])
            if row else "")


def _append_registry(db, person_id, zid, payload,
                     created_at):
    prev = _prev_hash(db, person_id)
    eh = _sha(prev + "|" + str(person_id)
              + "|" + payload + "|"
              + str(created_at))
    rid = ("AXREG-"
           + uuid.uuid4().hex[:10])
    db.execute(
        "INSERT INTO ax_crim_registry (reg_id,"
        " person_id, zid, payload, prev_hash,"
        " entry_hash, created_at)"
        " VALUES (?, ?, ?, ?, ?, ?, ?)",
        (rid, str(person_id), str(zid),
         payload, prev, eh, str(created_at)))
    return rid, eh


def convict_db(db, *, crim_id, charge,
               sentence_days=0, fine=0.0,
               dictated_by="", created_at=""):
    ensure_db(db)
    row = _case(db, crim_id)
    if str(row["status"]) != "abierto":
        raise ValueError(
            "condena solo en abierto")
    if not str(charge).strip():
        raise ValueError(
            "charge requerida")
    if int(sentence_days) < 0 or \
            float(fine) < 0:
        raise ValueError(
            "sentence/fine no negativos")
    vid = ("AXCV-"
           + uuid.uuid4().hex[:10])
    pid = str(row["person_id"])
    db.execute(
        "INSERT INTO ax_crim_conv (conv_id,"
        " crim_id, person_id, charge,"
        " sentence_days, fine, dictated_by,"
        " created_at) VALUES (?, ?, ?, ?, ?, ?,"
        " ?, ?)",
        (vid, str(crim_id), pid, str(charge),
         int(sentence_days), float(fine),
         str(dictated_by), str(created_at)))
    db.execute(
        "UPDATE ax_crim_cases SET status ="
        " 'condenado' WHERE crim_id = ?",
        (str(crim_id),))
    reg_id, eh = _append_registry(
        db, pid, str(row["zid"]),
        "CONDENA|" + str(charge) + "|"
        + str(sentence_days),
        str(created_at))
    return {"conv_id": vid,
            "reg_id": reg_id,
            "entry_hash": eh,
            "status": "condenado"}


def antecedentes_verify_db(db, person_id):
    ensure_db(db)
    rows = db.query_all(
        "SELECT person_id, payload, prev_hash,"
        " entry_hash, created_at FROM"
        " ax_crim_registry WHERE person_id = ?"
        " ORDER BY rowid", (str(person_id),))
    prev = ""
    for r in rows:
        expect = _sha(
            prev + "|" + str(r["person_id"])
            + "|" + str(r["payload"]) + "|"
            + str(r["created_at"]))
        if expect != str(r["entry_hash"]):
            return False
        if prev != str(r["prev_hash"]):
            return False
        prev = str(r["entry_hash"])
    return True


def antecedentes_cert_db(db, person_id):
    ensure_db(db)
    n = db.query_one(
        "SELECT COUNT(*) AS n FROM"
        " ax_crim_registry WHERE person_id = ?",
        (str(person_id),))
    zid = db.query_one(
        "SELECT zid FROM ax_crim_registry WHERE"
        " person_id = ? ORDER BY rowid DESC"
        " LIMIT 1", (str(person_id),))
    conv = db.query_one(
        "SELECT COUNT(*) AS n FROM"
        " ax_crim_conv WHERE person_id = ?",
        (str(person_id),))
    return {"person_id": str(person_id),
            "zid": (str(zid["zid"])
                    if zid is not None
                    else ""),
            "entries": int(n["n"]),
            "convictions": int(conv["n"]),
            "chain_verified":
                antecedentes_verify_db(
                    db, person_id)}


def reincidence_db(db, person_id):
    ensure_db(db)
    row = db.query_one(
        "SELECT COUNT(*) AS n FROM ax_crim_conv"
        " WHERE person_id = ?",
        (str(person_id),))
    n = int(row["n"])
    if n == 0:
        level = "PRIMARIO"
    elif n <= 2:
        level = "REINCIDENTE"
    else:
        level = "HABITUAL"
    return {"prior_convictions": n,
            "level": level}
