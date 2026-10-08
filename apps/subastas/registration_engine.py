
"""SUBASTAS Registration Engine (SUB-2) - KYC/KYB:
compradores con ZID (regla 63), vendedores/empresas
con tax_id, verificacion exige documento, decision
unica. Patron _DDL + ensure_db."""
from __future__ import annotations
import uuid
from shared_engines.storage.database import (
    Database)

_DDL = (
    "CREATE TABLE IF NOT EXISTS sb_subjects ("
    " subject_id TEXT PRIMARY KEY, kind TEXT NOT"
    " NULL, name TEXT NOT NULL, zid TEXT NOT NULL"
    " DEFAULT '', tax_id TEXT NOT NULL DEFAULT '',"
    " status TEXT NOT NULL DEFAULT 'pendiente',"
    " verified_by TEXT NOT NULL DEFAULT '',"
    " verified_at TEXT NOT NULL DEFAULT '', created"
    "_at TEXT NOT NULL DEFAULT '')",
    "CREATE TABLE IF NOT EXISTS sb_kyc_docs ("
    " doc_id TEXT PRIMARY KEY, subject_id TEXT NOT"
    " NULL, kind TEXT NOT NULL, ref TEXT NOT NULL"
    " DEFAULT '', created_at TEXT NOT NULL"
    " DEFAULT '')",
)
_KINDS = ("COMPRADOR", "VENDEDOR", "EMPRESA")


def ensure_db(db):
    for stmt in _DDL:
        db.execute(stmt)


def register_subject_db(db, *, kind, name,
                        zid="", tax_id="",
                        created_at=""):
    ensure_db(db)
    k = str(kind).upper()
    if k not in _KINDS:
        raise ValueError("kind debe ser "
                         + "/".join(_KINDS))
    if not str(name).strip():
        raise ValueError("name requerido")
    if k == "COMPRADOR" and not str(zid).strip():
        raise ValueError(
            "comprador requiere ZID")
    if k in ("VENDEDOR", "EMPRESA") and \
            not str(tax_id).strip():
        raise ValueError(
            "vendedor/empresa requiere"
            " tax_id")
    sid = ("SBS-"
           + uuid.uuid4().hex[:10])
    db.execute(
        "INSERT INTO sb_subjects (subject_id,"
        " kind, name, zid, tax_id, status,"
        " verified_by, verified_at, created_at)"
        " VALUES (?, ?, ?, ?, ?, 'pendiente', '',"
        " '', ?)",
        (sid, k, str(name), str(zid),
         str(tax_id), str(created_at)))
    return {"subject_id": sid,
            "status": "pendiente"}


def _subject(db, subject_id):
    row = db.query_one(
        "SELECT * FROM sb_subjects WHERE"
        " subject_id = ?", (str(subject_id),))
    if row is None:
        raise LookupError(
            "sujeto no encontrado: "
            + str(subject_id))
    return row


def add_doc_db(db, *, subject_id, kind, ref="",
               created_at=""):
    ensure_db(db)
    _subject(db, subject_id)
    if not str(kind).strip():
        raise ValueError("kind requerido")
    did = ("SBD-"
           + uuid.uuid4().hex[:10])
    db.execute(
        "INSERT INTO sb_kyc_docs (doc_id,"
        " subject_id, kind, ref, created_at)"
        " VALUES (?, ?, ?, ?, ?)",
        (did, str(subject_id), str(kind),
         str(ref), str(created_at)))
    return {"doc_id": did}


def verify_subject_db(db, subject_id, *,
                      approve, verified_by="",
                      at=""):
    ensure_db(db)
    row = _subject(db, subject_id)
    if str(row["status"]) != "pendiente":
        raise ValueError(
            "ya verificado")
    if not str(verified_by).strip():
        raise ValueError(
            "verified_by requerido")
    n = db.query_one(
        "SELECT COUNT(*) AS n FROM sb_kyc_docs"
        " WHERE subject_id = ?",
        (str(subject_id),))
    if approve and int(n["n"]) < 1:
        raise ValueError(
            "aprobacion exige al menos 1"
            " documento (regla 66)")
    new = "verificado" if approve \
        else "rechazado"
    db.execute(
        "UPDATE sb_subjects SET status = ?,"
        " verified_by = ?, verified_at = ? WHERE"
        " subject_id = ?",
        (new, str(verified_by), str(at),
         str(subject_id)))
    return {"subject_id": str(subject_id),
            "status": new}


def subject_of_db(db, subject_id):
    ensure_db(db)
    row = _subject(db, subject_id)
    return {"subject_id": str(
                row["subject_id"]),
            "kind": str(row["kind"]),
            "name": str(row["name"]),
            "zid": str(row["zid"]),
            "status": str(row["status"])}


def verified_subjects_db(db, kind=""):
    ensure_db(db)
    if str(kind).strip():
        rows = db.query_all(
            "SELECT subject_id, kind, name, zid"
            " FROM sb_subjects WHERE status ="
            " 'verificado' AND kind = ? ORDER BY"
            " rowid", (str(kind).upper(),))
    else:
        rows = db.query_all(
            "SELECT subject_id, kind, name, zid"
            " FROM sb_subjects WHERE status ="
            " 'verificado' ORDER BY rowid")
    return [{"subject_id": str(
                 r["subject_id"]),
             "kind": str(r["kind"]),
             "name": str(r["name"])}
            for r in rows]
