
"""AXIS Forensic Lab (AX-8): peritajes con ref
obligatoria, hallazgos, informe que cierra. Patron
_DDL + ensure_db."""
from __future__ import annotations
import uuid
from shared_engines.storage.database import (
    Database)

_DDL = (
    "CREATE TABLE IF NOT EXISTS ax_fx_cases ("
    " fx_id TEXT PRIMARY KEY, kind TEXT NOT NULL,"
    " ref_case_id TEXT NOT NULL DEFAULT '',"
    " ref_incident_id TEXT NOT NULL DEFAULT '',"
    " status TEXT NOT NULL DEFAULT 'ingresado',"
    " created_at TEXT NOT NULL DEFAULT '')",
    "CREATE TABLE IF NOT EXISTS ax_fx_findings ("
    " finding_id TEXT PRIMARY KEY, fx_id TEXT NOT"
    " NULL, expert TEXT NOT NULL, finding TEXT"
    " NOT NULL, confidence TEXT NOT NULL DEFAULT"
    " '', recorded_at TEXT NOT NULL DEFAULT '')",
    "CREATE TABLE IF NOT EXISTS ax_fx_reports ("
    " report_id TEXT PRIMARY KEY, fx_id TEXT NOT"
    " NULL, conclusion TEXT NOT NULL, signed_by"
    " TEXT NOT NULL, issued_at TEXT NOT NULL"
    " DEFAULT '')",
)
_KINDS = ("ADN", "HUELLA", "BALISTICA",
          "TOXICOLOGIA", "AUTOPSIA", "DIGITAL")


def ensure_db(db):
    for stmt in _DDL:
        db.execute(stmt)


def open_fx_db(db, *, kind, ref_case_id="",
               ref_incident_id="",
               created_at=""):
    ensure_db(db)
    k = str(kind).upper()
    if k not in _KINDS:
        raise ValueError("kind debe ser "
                         + "/".join(_KINDS))
    if not str(ref_case_id).strip() and \
            not str(ref_incident_id).strip():
        raise ValueError(
            "peritaje exige ref a caso o"
            " incidente")
    fid = ("AXFX-"
           + uuid.uuid4().hex[:10])
    db.execute(
        "INSERT INTO ax_fx_cases (fx_id, kind,"
        " ref_case_id, ref_incident_id, status,"
        " created_at) VALUES (?, ?, ?, ?,"
        " 'ingresado', ?)",
        (fid, k, str(ref_case_id),
         str(ref_incident_id),
         str(created_at)))
    return {"fx_id": fid, "kind": k,
            "status": "ingresado"}


def _fx(db, fx_id):
    row = db.query_one(
        "SELECT fx_id, status FROM ax_fx_cases"
        " WHERE fx_id = ?", (str(fx_id),))
    if row is None:
        raise LookupError(
            "peritaje no encontrado: "
            + str(fx_id))
    return row


def add_finding_db(db, *, fx_id, expert, finding,
                   confidence="",
                   recorded_at=""):
    ensure_db(db)
    row = _fx(db, fx_id)
    if str(row["status"]) == "informe":
        raise ValueError(
            "peritaje cerrado")
    if not str(expert).strip() or \
            not str(finding).strip():
        raise ValueError(
            "expert y finding requeridos")
    if str(row["status"]) == "ingresado":
        db.execute(
            "UPDATE ax_fx_cases SET status ="
            " 'en_proceso' WHERE fx_id = ?",
            (str(fx_id),))
    fid = ("AXFF-"
           + uuid.uuid4().hex[:10])
    db.execute(
        "INSERT INTO ax_fx_findings (finding_id,"
        " fx_id, expert, finding, confidence,"
        " recorded_at) VALUES (?, ?, ?, ?, ?, ?)",
        (fid, str(fx_id), str(expert),
         str(finding), str(confidence),
         str(recorded_at)))
    return {"finding_id": fid}


def issue_report_db(db, fx_id, *, conclusion,
                    signed_by, issued_at=""):
    ensure_db(db)
    row = _fx(db, fx_id)
    if str(row["status"]) == "informe":
        raise ValueError(
            "informe ya emitido")
    n = db.query_one(
        "SELECT COUNT(*) AS n FROM"
        " ax_fx_findings WHERE fx_id = ?",
        (str(fx_id),))
    if int(n["n"]) < 1:
        raise ValueError(
            "informe exige hallazgo")
    if not str(conclusion).strip() or \
            not str(signed_by).strip():
        raise ValueError(
            "conclusion y firma requeridas")
    rid = ("AXFR-"
           + uuid.uuid4().hex[:10])
    db.execute(
        "INSERT INTO ax_fx_reports (report_id,"
        " fx_id, conclusion, signed_by,"
        " issued_at) VALUES (?, ?, ?, ?, ?)",
        (rid, str(fx_id), str(conclusion),
         str(signed_by), str(issued_at)))
    db.execute(
        "UPDATE ax_fx_cases SET status ="
        " 'informe' WHERE fx_id = ?",
        (str(fx_id),))
    return {"report_id": rid,
            "status": "informe"}


def findings_of_db(db, fx_id):
    ensure_db(db)
    rows = db.query_all(
        "SELECT finding_id, expert, finding,"
        " confidence, recorded_at FROM"
        " ax_fx_findings WHERE fx_id = ? ORDER"
        " BY rowid", (str(fx_id),))
    return [{"finding_id": str(
                 r["finding_id"]),
             "expert": str(r["expert"]),
             "finding": str(r["finding"]),
             "confidence": str(
                 r["confidence"])}
            for r in rows]


def fxs_by_ref_db(db, ref_id):
    ensure_db(db)
    rows = db.query_all(
        "SELECT fx_id, kind, status, ref_case_id,"
        " ref_incident_id FROM ax_fx_cases WHERE"
        " ref_case_id = ? OR ref_incident_id = ?"
        " ORDER BY rowid", (str(ref_id),
                            str(ref_id)))
    return [{"fx_id": str(r["fx_id"]),
             "kind": str(r["kind"]),
             "status": str(r["status"])}
            for r in rows]
