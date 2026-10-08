
"""AXIS Health EHR (AX-5): expediente clinico con
ZID + recetas. Patron _DDL + ensure_db."""
from __future__ import annotations
import uuid
from shared_engines.storage.database import (
    Database)

_DDL = (
    "CREATE TABLE IF NOT EXISTS ax_health_rec ("
    " rec_id TEXT PRIMARY KEY, person_id TEXT NOT"
    " NULL, kind TEXT NOT NULL, detail TEXT NOT"
    " NULL DEFAULT '', code TEXT NOT NULL DEFAULT"
    " '', actor TEXT NOT NULL DEFAULT '',"
    " recorded_at TEXT NOT NULL DEFAULT '')",
    "CREATE TABLE IF NOT EXISTS ax_health_rx ("
    " rx_id TEXT PRIMARY KEY, person_id TEXT NOT"
    " NULL, medication TEXT NOT NULL, dose TEXT"
    " NOT NULL DEFAULT '', days INTEGER NOT NULL"
    " DEFAULT 0, prescribed_by TEXT NOT NULL,"
    " rec_id TEXT NOT NULL DEFAULT '', issued_at"
    " TEXT NOT NULL DEFAULT '')",
)
_KINDS = ("DIAGNOSTICO", "MEDICAMENTO",
          "ALERGIA", "VACUNA", "CRONICO",
          "CIRUGIA", "HOSPITALIZACION",
          "REFERENCIA")


def ensure_db(db):
    for stmt in _DDL:
        db.execute(stmt)


def add_record_db(db, *, person_id, kind,
                  detail="", code="", actor="",
                  recorded_at=""):
    ensure_db(db)
    if not str(person_id).strip():
        raise ValueError(
            "person_id requerido")
    k = str(kind).upper()
    if k not in _KINDS:
        raise ValueError("kind debe ser "
                         + "/".join(_KINDS))
    if not str(detail).strip():
        raise ValueError(
            "detail requerido")
    rid = ("AXHR-"
           + uuid.uuid4().hex[:10])
    db.execute(
        "INSERT INTO ax_health_rec (rec_id,"
        " person_id, kind, detail, code, actor,"
        " recorded_at) VALUES (?, ?, ?, ?, ?, ?,"
        " ?)",
        (rid, str(person_id), k, str(detail),
         str(code), str(actor),
         str(recorded_at)))
    return {"rec_id": rid, "kind": k}


def records_of_db(db, person_id, kind=""):
    ensure_db(db)
    if str(kind).strip():
        rows = db.query_all(
            "SELECT rec_id, kind, detail, code,"
            " actor, recorded_at FROM"
            " ax_health_rec WHERE person_id = ?"
            " AND kind = ? ORDER BY rowid",
            (str(person_id),
             str(kind).upper()))
    else:
        rows = db.query_all(
            "SELECT rec_id, kind, detail, code,"
            " actor, recorded_at FROM"
            " ax_health_rec WHERE person_id = ?"
            " ORDER BY rowid", (str(person_id),))
    return [{"rec_id": str(r["rec_id"]),
             "kind": str(r["kind"]),
             "detail": str(r["detail"]),
             "code": str(r["code"]),
             "recorded_at": str(
                 r["recorded_at"])}
            for r in rows]


def add_prescription_db(db, *, person_id,
                        medication, dose="",
                        days=0, prescribed_by="",
                        rec_id="", issued_at=""):
    ensure_db(db)
    if not str(medication).strip():
        raise ValueError(
            "medication requerida")
    if int(days) < 0:
        raise ValueError("days no negativos")
    if not str(prescribed_by).strip():
        raise ValueError(
            "prescribed_by requerido")
    rid = ("AXRX-"
           + uuid.uuid4().hex[:10])
    db.execute(
        "INSERT INTO ax_health_rx (rx_id,"
        " person_id, medication, dose, days,"
        " prescribed_by, rec_id, issued_at)"
        " VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
        (rid, str(person_id), str(medication),
         str(dose), int(days),
         str(prescribed_by), str(rec_id),
         str(issued_at)))
    return {"rx_id": rid,
            "medication": str(medication)}


def prescriptions_of_db(db, person_id):
    ensure_db(db)
    rows = db.query_all(
        "SELECT rx_id, medication, dose, days,"
        " prescribed_by, issued_at FROM"
        " ax_health_rx WHERE person_id = ? ORDER"
        " BY rowid", (str(person_id),))
    return [{"rx_id": str(r["rx_id"]),
             "medication": str(
                 r["medication"]),
             "dose": str(r["dose"]),
             "days": int(r["days"]),
             "issued_at": str(
                 r["issued_at"])}
            for r in rows]


def ehr_summary_db(db, person_id):
    ensure_db(db)
    rows = db.query_all(
        "SELECT kind, COUNT(*) AS n FROM"
        " ax_health_rec WHERE person_id = ?"
        " GROUP BY kind", (str(person_id),))
    by_kind = {str(r["kind"]): int(r["n"])
               for r in rows}
    allergies = [
        str(r["detail"]) for r in
        db.query_all(
            "SELECT detail FROM ax_health_rec"
            " WHERE person_id = ? AND kind ="
            " 'ALERGIA' ORDER BY rowid",
            (str(person_id),))]
    vaccines = [
        str(r["detail"]) for r in
        db.query_all(
            "SELECT detail FROM ax_health_rec"
            " WHERE person_id = ? AND kind ="
            " 'VACUNA' ORDER BY rowid",
            (str(person_id),))]
    chronic = [
        str(r["detail"]) for r in
        db.query_all(
            "SELECT detail FROM ax_health_rec"
            " WHERE person_id = ? AND kind ="
            " 'CRONICO' ORDER BY rowid",
            (str(person_id),))]
    n_rx = db.query_one(
        "SELECT COUNT(*) AS n FROM ax_health_rx"
        " WHERE person_id = ?",
        (str(person_id),))
    return {"person_id": str(person_id),
            "by_kind": by_kind,
            "allergies": allergies,
            "vaccines": vaccines,
            "chronic": chronic,
            "prescriptions": int(n_rx["n"])}
