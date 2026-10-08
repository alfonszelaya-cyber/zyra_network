
"""AX-16 Biometric Registry: dispositivos,
enrolamiento al MISMO ZID (regla 78) con hash de
template (regla 63), verificacion 1:1
verify_identity, identificacion 1:N, reemplazo,
revocacion CON motivo. Patron _DDL + ensure_db."""
from __future__ import annotations
import hashlib
import uuid
from shared_engines.storage.database import (
    Database)

_DDL = (
    "CREATE TABLE IF NOT EXISTS ax_biometrics ("
    " bio_id TEXT PRIMARY KEY, person_id TEXT NOT"
    " NULL, zid TEXT NOT NULL DEFAULT '', kind"
    " TEXT NOT NULL, template_hash TEXT NOT NULL,"
    " device_id TEXT NOT NULL DEFAULT '', quality"
    " INTEGER NOT NULL DEFAULT 0, status TEXT NOT"
    " NULL DEFAULT 'activa', created_at TEXT NOT"
    " NULL DEFAULT '')",
    "CREATE TABLE IF NOT EXISTS ax_bio_devices ("
    " device_id TEXT PRIMARY KEY, kind TEXT NOT"
    " NULL, location TEXT NOT NULL DEFAULT '',"
    " active INTEGER NOT NULL DEFAULT 1, created"
    "_at TEXT NOT NULL DEFAULT '')",
)
_KINDS = ("HUELLA", "ROSTRO", "IRIS")


def ensure_db(db):
    for stmt in _DDL:
        db.execute(stmt)


def register_device_db(db, *, device_id, kind,
                       location="",
                       created_at=""):
    ensure_db(db)
    if not str(device_id).strip():
        raise ValueError(
            "device_id requerido")
    k = str(kind).upper()
    if k not in _KINDS:
        raise ValueError("kind debe ser "
                         + "/".join(_KINDS))
    dup = db.query_one(
        "SELECT device_id FROM ax_bio_devices"
        " WHERE device_id = ?",
        (str(device_id),))
    if dup is not None:
        raise ValueError(
            "dispositivo ya registrado")
    db.execute(
        "INSERT INTO ax_bio_devices (device_id,"
        " kind, location, active, created_at)"
        " VALUES (?, ?, ?, 1, ?)",
        (str(device_id), k, str(location),
         str(created_at)))
    return {"device_id": str(device_id)}


def enroll_db(db, *, person_id, zid="", kind,
              template_b64, device_id="",
              quality=0, at=""):
    ensure_db(db)
    if not str(person_id).strip():
        raise ValueError(
            "person_id requerido (regla 78)")
    k = str(kind).upper()
    if k not in _KINDS:
        raise ValueError("kind debe ser "
                         + "/".join(_KINDS))
    if not str(template_b64).strip():
        raise ValueError(
            "template_b64 requerido")
    th = hashlib.sha256(
        str(template_b64).encode(
            "utf-8")).hexdigest()
    dup = db.query_one(
        "SELECT bio_id FROM ax_biometrics WHERE"
        " person_id = ? AND kind = ? AND status"
        " = 'activa'", (str(person_id), k))
    if dup is not None:
        db.execute(
            "UPDATE ax_biometrics SET status ="
            " 'reemplazada' WHERE bio_id = ?",
            (str(dup["bio_id"]),))
    bid = ("AXB-"
           + uuid.uuid4().hex[:10])
    db.execute(
        "INSERT INTO ax_biometrics (bio_id,"
        " person_id, zid, kind, template_hash,"
        " device_id, quality, status, created_at)"
        " VALUES (?, ?, ?, ?, ?, ?, ?, 'activa',"
        " ?)",
        (bid, str(person_id), str(zid), k, th,
         str(device_id), int(quality),
         str(at)))
    return {"bio_id": bid,
            "template_hash": th}


def verify_identity(db, *, person_id, kind,
                    template_b64):
    ensure_db(db)
    k = str(kind).upper()
    th = hashlib.sha256(
        str(template_b64).encode(
            "utf-8")).hexdigest()
    row = db.query_one(
        "SELECT bio_id, template_hash FROM"
        " ax_biometrics WHERE person_id = ? AND"
        " kind = ? AND status = 'activa'",
        (str(person_id), k))
    if row is None:
        return {"matched": False,
                "reason": "sin plantilla"
                          " activa"}
    matched = (str(row["template_hash"])
               == th)
    return {"matched": matched,
            "bio_id": str(row["bio_id"])}


def identify_db(db, *, kind, template_b64):
    ensure_db(db)
    k = str(kind).upper()
    th = hashlib.sha256(
        str(template_b64).encode(
            "utf-8")).hexdigest()
    row = db.query_one(
        "SELECT person_id, zid FROM"
        " ax_biometrics WHERE kind = ? AND"
        " template_hash = ? AND status ="
        " 'activa' LIMIT 1", (k, th))
    if row is None:
        return {"matched": False}
    return {"matched": True,
            "person_id": str(
                row["person_id"]),
            "zid": str(row["zid"])}


def revoke_bio_db(db, bio_id, *, reason="",
                  at=""):
    ensure_db(db)
    row = db.query_one(
        "SELECT status FROM ax_biometrics WHERE"
        " bio_id = ?", (str(bio_id),))
    if row is None:
        raise KeyError(bio_id)
    if str(row["status"]) != "activa":
        raise ValueError("no activa")
    db.execute(
        "UPDATE ax_biometrics SET status ="
        " 'revocada' WHERE bio_id = ?",
        (str(bio_id),))
    return {"bio_id": str(bio_id),
            "status": "revocada"}


def biometrics_of_db(db, person_id):
    ensure_db(db)
    rows = db.query_all(
        "SELECT bio_id, kind, status, quality"
        " FROM ax_biometrics WHERE person_id = ?"
        " ORDER BY rowid", (str(person_id),))
    return [{"bio_id": str(r["bio_id"]),
             "kind": str(r["kind"]),
             "status": str(r["status"])}
            for r in rows]
