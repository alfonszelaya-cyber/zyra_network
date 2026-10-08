
"""AXIS Justice Extended (AX-4): resoluciones,
recursos, medidas, ordenes, correspondencia (regla
79), prision con ZID (exige sentencia, regla 66),
estado de procesos. Patron _DDL + ensure_db."""
from __future__ import annotations
import uuid
from shared_engines.storage.database import (
    Database)

_DDL = (
    "CREATE TABLE IF NOT EXISTS ax_justice_res ("
    " res_id TEXT PRIMARY KEY, case_id TEXT NOT"
    " NULL, kind TEXT NOT NULL, judge TEXT NOT"
    " NULL, body TEXT NOT NULL DEFAULT '',"
    " issued_at TEXT NOT NULL DEFAULT '')",
    "CREATE TABLE IF NOT EXISTS ax_justice_rec ("
    " rec_id TEXT PRIMARY KEY, case_id TEXT NOT"
    " NULL, kind TEXT NOT NULL, base TEXT NOT"
    " NULL DEFAULT '', filed_by TEXT NOT NULL,"
    " outcome TEXT NOT NULL DEFAULT 'pendiente',"
    " resolved_by TEXT NOT NULL DEFAULT '',"
    " created_at TEXT NOT NULL DEFAULT '')",
    "CREATE TABLE IF NOT EXISTS ax_justice_med ("
    " med_id TEXT PRIMARY KEY, case_id TEXT NOT"
    " NULL, kind TEXT NOT NULL, target_person TEXT"
    " NOT NULL, detail TEXT NOT NULL DEFAULT '',"
    " status TEXT NOT NULL DEFAULT 'activa',"
    " issued_by TEXT NOT NULL, lifted_at TEXT NOT"
    " NULL DEFAULT '', issued_at TEXT NOT NULL"
    " DEFAULT '')",
    "CREATE TABLE IF NOT EXISTS ax_justice_ord ("
    " ord_id TEXT PRIMARY KEY, case_id TEXT NOT"
    " NULL DEFAULT '', kind TEXT NOT NULL,"
    " target_person TEXT NOT NULL DEFAULT '',"
    " issued_by TEXT NOT NULL, status TEXT NOT"
    " NULL DEFAULT 'emitida', executed_by TEXT"
    " NOT NULL DEFAULT '', executed_at TEXT NOT"
    " NULL DEFAULT '', issued_at TEXT NOT NULL"
    " DEFAULT '')",
    "CREATE TABLE IF NOT EXISTS ax_justice_mail ("
    " mail_id TEXT PRIMARY KEY, case_id TEXT NOT"
    " NULL DEFAULT '', to_account TEXT NOT NULL,"
    " subject TEXT NOT NULL, body TEXT NOT NULL"
    " DEFAULT '', sent_at TEXT NOT NULL DEFAULT"
    " '')",
    "CREATE TABLE IF NOT EXISTS ax_justice_pris ("
    " pris_id TEXT PRIMARY KEY, case_id TEXT NOT"
    " NULL, person_id TEXT NOT NULL, zid TEXT NOT"
    " NULL DEFAULT '', sentence_days INTEGER NOT"
    " NULL DEFAULT 0, status TEXT NOT NULL DEFAULT"
    " 'preso', entry_by TEXT NOT NULL, entry_at"
    " TEXT NOT NULL DEFAULT '', exit_at TEXT NOT"
    " NULL DEFAULT '')",
)
_RES = ("SENTENCIA", "AUTO", "DECRETO",
        "EXHORTO")
_REC = ("APELACION", "CASACION", "REVISION")
_MED = ("PROHIBICION", "PRISION_PREVENTIVA",
        "INMOVILIZACION", "SUSPENSION")
_ORD = ("ORDEN_JUDICIAL", "ORDEN_CAPTURA")


def ensure_db(db):
    for stmt in _DDL:
        db.execute(stmt)


def issue_resolucion_db(db, *, case_id, kind,
                        judge, body="",
                        issued_at=""):
    ensure_db(db)
    k = str(kind).upper()
    if k not in _RES:
        raise ValueError("kind debe ser "
                         + "/".join(_RES))
    if not str(judge).strip():
        raise ValueError("judge requerido")
    rid = ("AXR-"
           + uuid.uuid4().hex[:10])
    db.execute(
        "INSERT INTO ax_justice_res (res_id,"
        " case_id, kind, judge, body, issued_at)"
        " VALUES (?, ?, ?, ?, ?, ?)",
        (rid, str(case_id), k, str(judge),
         str(body), str(issued_at)))
    return {"res_id": rid, "case_id":
            str(case_id), "kind": k}


def res_of_db(db, case_id):
    ensure_db(db)
    rows = db.query_all(
        "SELECT res_id, kind, judge, body,"
        " issued_at FROM ax_justice_res WHERE"
        " case_id = ? ORDER BY rowid",
        (str(case_id),))
    return [{"res_id": str(r["res_id"]),
             "kind": str(r["kind"]),
             "judge": str(r["judge"]),
             "body": str(r["body"]),
             "issued_at": str(r["issued_at"])}
            for r in rows]


def file_recurso_db(db, *, case_id, kind, base,
                    filed_by, created_at=""):
    ensure_db(db)
    k = str(kind).upper()
    if k not in _REC:
        raise ValueError("kind debe ser "
                         + "/".join(_REC))
    if not str(base).strip():
        raise ValueError(
            "base del recurso requerida")
    sid = ("AXRC-"
           + uuid.uuid4().hex[:10])
    db.execute(
        "INSERT INTO ax_justice_rec (rec_id,"
        " case_id, kind, base, filed_by, outcome,"
        " resolved_by, created_at)"
        " VALUES (?, ?, ?, ?, ?, 'pendiente',"
        " '', ?)",
        (sid, str(case_id), k, str(base),
         str(filed_by), str(created_at)))
    return {"rec_id": sid, "kind": k,
            "outcome": "pendiente"}


def resolve_recurso_db(db, rec_id, *, outcome,
                       resolved_by):
    ensure_db(db)
    row = db.query_one(
        "SELECT outcome FROM ax_justice_rec WHERE"
        " rec_id = ?", (str(rec_id),))
    if row is None:
        raise KeyError(rec_id)
    if str(row["outcome"]) != "pendiente":
        raise ValueError(
            "recurso ya resuelto")
    o = str(outcome).upper()
    if o not in ("CONFIRMADA", "REVOCADA",
                 "PARCIAL"):
        raise ValueError(
            "outcome CONFIRMADA/REVOCADA/"
            "PARCIAL")
    db.execute(
        "UPDATE ax_justice_rec SET outcome = ?,"
        " resolved_by = ? WHERE rec_id = ?",
        (o, str(resolved_by), str(rec_id)))
    return {"rec_id": str(rec_id),
            "outcome": o}


def issue_medida_db(db, *, case_id, kind,
                    target_person, detail="",
                    issued_by="",
                    issued_at=""):
    ensure_db(db)
    k = str(kind).upper()
    if k not in _MED:
        raise ValueError("kind debe ser "
                         + "/".join(_MED))
    if not str(target_person).strip():
        raise ValueError(
            "target_person requerido")
    mid = ("AXM-"
           + uuid.uuid4().hex[:10])
    db.execute(
        "INSERT INTO ax_justice_med (med_id,"
        " case_id, kind, target_person, detail,"
        " status, issued_by, lifted_at, issued_at)"
        " VALUES (?, ?, ?, ?, ?, 'activa', ?,"
        " '', ?)",
        (mid, str(case_id), k,
         str(target_person), str(detail),
         str(issued_by), str(issued_at)))
    return {"med_id": mid, "kind": k,
            "status": "activa"}


def lift_medida_db(db, med_id, *, lifted_at=""):
    ensure_db(db)
    row = db.query_one(
        "SELECT status FROM ax_justice_med WHERE"
        " med_id = ?", (str(med_id),))
    if row is None:
        raise KeyError(med_id)
    if str(row["status"]) != "activa":
        raise ValueError(
            "medida ya levantada")
    db.execute(
        "UPDATE ax_justice_med SET status ="
        " 'levantada', lifted_at = ? WHERE"
        " med_id = ?",
        (str(lifted_at), str(med_id)))
    return {"med_id": str(med_id),
            "status": "levantada"}


def issue_orden_db(db, *, kind, case_id="",
                   target_person="",
                   issued_by="",
                   issued_at=""):
    ensure_db(db)
    k = str(kind).upper()
    if k not in _ORD:
        raise ValueError("kind debe ser "
                         + "/".join(_ORD))
    if k == "ORDEN_CAPTURA" and \
            not str(target_person).strip():
        raise ValueError(
            "ORDEN_CAPTURA exige target")
    oid = ("AXO-"
           + uuid.uuid4().hex[:10])
    db.execute(
        "INSERT INTO ax_justice_ord (ord_id,"
        " case_id, kind, target_person, issued_by,"
        " status, executed_by, executed_at,"
        " issued_at) VALUES (?, ?, ?, ?, ?,"
        " 'emitida', '', '', ?)",
        (oid, str(case_id), k,
         str(target_person), str(issued_by),
         str(issued_at)))
    return {"ord_id": oid, "kind": k,
            "status": "emitida"}


def execute_orden_db(db, ord_id, *,
                     executed_by="",
                     executed_at=""):
    ensure_db(db)
    row = db.query_one(
        "SELECT status FROM ax_justice_ord WHERE"
        " ord_id = ?", (str(ord_id),))
    if row is None:
        raise KeyError(ord_id)
    if str(row["status"]) != "emitida":
        raise ValueError(
            "orden ya ejecutada")
    db.execute(
        "UPDATE ax_justice_ord SET status ="
        " 'ejecutada', executed_by = ?,"
        " executed_at = ? WHERE ord_id = ?",
        (str(executed_by), str(executed_at),
         str(ord_id)))
    return {"ord_id": str(ord_id),
            "status": "ejecutada"}


def send_mail_db(db, *, to_account, subject,
                 case_id="", body="",
                 sent_at=""):
    ensure_db(db)
    if not str(to_account).strip() or \
            not str(subject).strip():
        raise ValueError(
            "to_account y subject requeridos")
    mid = ("AXMAIL-"
           + uuid.uuid4().hex[:10])
    db.execute(
        "INSERT INTO ax_justice_mail (mail_id,"
        " case_id, to_account, subject, body,"
        " sent_at) VALUES (?, ?, ?, ?, ?, ?)",
        (mid, str(case_id), str(to_account),
         str(subject), str(body),
         str(sent_at)))
    return {"mail_id": mid,
            "to_account": str(to_account)}


def mail_of_db(db, to_account):
    ensure_db(db)
    rows = db.query_all(
        "SELECT mail_id, case_id, subject, body,"
        " sent_at FROM ax_justice_mail WHERE"
        " to_account = ? ORDER BY rowid",
        (str(to_account),))
    return [{"mail_id": str(r["mail_id"]),
             "case_id": str(r["case_id"]),
             "subject": str(r["subject"]),
             "body": str(r["body"]),
             "sent_at": str(r["sent_at"])}
            for r in rows]


def imprison_db(db, *, case_id, person_id,
                zid="", sentence_days=0,
                entry_by="", entry_at=""):
    ensure_db(db)
    row = db.query_one(
        "SELECT COUNT(*) AS n FROM"
        " ax_justice_res WHERE case_id = ? AND"
        " kind = 'SENTENCIA'",
        (str(case_id),))
    if int(row["n"]) < 1:
        raise ValueError(
            "prision exige SENTENCIA previa"
            " (regla 66)")
    if not str(person_id).strip():
        raise ValueError(
            "person_id requerido")
    if int(sentence_days) < 0:
        raise ValueError(
            "sentence_days no negativos")
    pid = ("AXP-"
           + uuid.uuid4().hex[:10])
    db.execute(
        "INSERT INTO ax_justice_pris (pris_id,"
        " case_id, person_id, zid, sentence_days,"
        " status, entry_by, entry_at, exit_at)"
        " VALUES (?, ?, ?, ?, ?, 'preso', ?, ?,"
        " '')",
        (pid, str(case_id), str(person_id),
         str(zid), int(sentence_days),
         str(entry_by), str(entry_at)))
    return {"pris_id": pid, "status": "preso",
            "person_id": str(person_id),
            "zid": str(zid)}


def release_prision_db(db, pris_id, *,
                       exit_at=""):
    ensure_db(db)
    row = db.query_one(
        "SELECT status FROM ax_justice_pris WHERE"
        " pris_id = ?", (str(pris_id),))
    if row is None:
        raise KeyError(pris_id)
    if str(row["status"]) != "preso":
        raise ValueError("ya liberado")
    db.execute(
        "UPDATE ax_justice_pris SET status ="
        " 'libre', exit_at = ? WHERE pris_id ="
        " ?", (str(exit_at), str(pris_id)))
    return {"pris_id": str(pris_id),
            "status": "libre"}


def condenados_db(db, only_activos=True):
    ensure_db(db)
    if only_activos:
        rows = db.query_all(
            "SELECT pris_id, case_id, person_id,"
            " zid, sentence_days, status FROM"
            " ax_justice_pris WHERE status ="
            " 'preso' ORDER BY rowid")
    else:
        rows = db.query_all(
            "SELECT pris_id, case_id, person_id,"
            " zid, sentence_days, status FROM"
            " ax_justice_pris ORDER BY rowid")
    return [{"pris_id": str(r["pris_id"]),
             "case_id": str(r["case_id"]),
             "person_id": str(r["person_id"]),
             "zid": str(r["zid"]),
             "sentence_days": int(
                 r["sentence_days"]),
             "status": str(r["status"])}
            for r in rows]


def estado_procesos_db(db, case_id=""):
    ensure_db(db)
    if str(case_id).strip():
        ids = [str(case_id)]
    else:
        rows = db.query_all(
            "SELECT case_id FROM"
            " ax_justice_res UNION SELECT"
            " case_id FROM ax_justice_rec UNION"
            " SELECT case_id FROM ax_justice_med"
            " UNION SELECT case_id FROM"
            " ax_justice_ord UNION SELECT"
            " case_id FROM ax_justice_pris")
        ids = sorted(set(
            str(r["case_id"]) for r in rows
            if str(r["case_id"]).strip()))
    out = []
    for cid in ids:
        def cnt(t):
            r = db.query_one(
                "SELECT COUNT(*) AS n FROM "
                + t + " WHERE case_id = ?",
                (cid,))
            return int(r["n"])
        pr = db.query_one(
            "SELECT status FROM"
            " ax_justice_pris WHERE case_id = ?"
            " ORDER BY rowid DESC LIMIT 1",
            (cid,))
        out.append({
            "case_id": cid,
            "resoluciones": cnt(
                "ax_justice_res"),
            "recursos": cnt(
                "ax_justice_rec"),
            "medidas": cnt(
                "ax_justice_med"),
            "ordenes": cnt(
                "ax_justice_ord"),
            "prision": (str(pr["status"])
                        if pr is not None
                        else "")})
    return out
