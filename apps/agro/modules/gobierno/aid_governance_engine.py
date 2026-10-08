
"""Aid Governance Engine (A-14): gobierno agrícola
sobre el ciclo de ayuda EXISTENTE (agro_aid_requests
+ agro_aid_events, DDL confirmado del AgroStore v3)
— ELEGIBILIDAD explicita (set con motivo), DETECCION
de DUPLICADOS (mismo productor+programa+item activos
o ya aprobados) y metricas de IMPACTO. Transiciones
registran evento. Patron _DDL + ensure_db."""
from __future__ import annotations
import uuid
from apps.agro.shared.money import safe_float as _sf
from shared_engines.storage.database import Database

_DDL = (
    "CREATE TABLE IF NOT EXISTS agro_aid_requests ("
    " aid_id TEXT PRIMARY KEY, producer_id TEXT NOT"
    " NULL, zid TEXT, program TEXT NOT NULL, item"
    " TEXT NOT NULL, quantity REAL NOT NULL, status"
    " TEXT NOT NULL DEFAULT 'requested', eligibility"
    " TEXT, created_at REAL NOT NULL, updated_at"
    " REAL NOT NULL)",
    "CREATE TABLE IF NOT EXISTS agro_aid_events ("
    " event_id TEXT PRIMARY KEY, aid_id TEXT NOT"
    " NULL, transition TEXT NOT NULL, actor TEXT"
    " NOT NULL, detail TEXT, network_seq INTEGER,"
    " created_at REAL NOT NULL)",
)


def ensure_db(db):
    for stmt in _DDL:
        db.execute(stmt)


def _aid(db, aid_id):
    row = db.query_one(
        "SELECT * FROM agro_aid_requests WHERE"
        " aid_id = ?", (str(aid_id),))
    if row is None:
        raise LookupError(
            "solicitud no encontrada: "
            + str(aid_id))
    return row


def _event(db, aid_id, transition, actor, detail,
           now):
    db.execute(
        "INSERT INTO agro_aid_events (event_id,"
        " aid_id, transition, actor, detail,"
        " network_seq, created_at)"
        " VALUES (?, ?, ?, ?, ?, NULL, ?)",
        ("AIDE-" + uuid.uuid4().hex[:10],
         str(aid_id), str(transition),
         str(actor), str(detail or ""),
         float(now)))


def set_eligibility_db(db, *, aid_id, eligible,
                       reason, actor="gobierno",
                       now=0.0):
    ensure_db(db)
    row = _aid(db, aid_id)
    if str(row["status"]) != "requested":
        raise ValueError(
            "elegibilidad solo en requested;"
            " estado: " + str(row["status"]))
    if not str(reason).strip():
        raise ValueError(
            "motivo obligatorio (regla 66)")
    tag = "ELIGIBLE" if eligible else "NO_ELIGIBLE"
    db.execute(
        "UPDATE agro_aid_requests SET eligibility ="
        " ?, updated_at = ? WHERE aid_id = ?",
        (tag + ": " + str(reason), float(now),
         str(aid_id)))
    _event(db, aid_id, "ELIGIBILITY_" + tag,
           actor, reason, now)
    return {"aid_id": str(aid_id),
            "eligibility": tag}


def decide_db(db, *, aid_id, approve,
              actor="gobierno", now=0.0):
    ensure_db(db)
    row = _aid(db, aid_id)
    el = str(row["eligibility"] or "")
    if not el.startswith("ELIGIBLE"):
        raise ValueError(
            "decide exige elegibilidad previa"
            " ELIGIBLE; actual: "
            + (el or "SIN_EVALUAR"))
    status = str(row["status"])
    if status != "requested":
        raise ValueError("estado: " + status)
    new = "approved" if approve else "rejected"
    db.execute(
        "UPDATE agro_aid_requests SET status = ?,"
        " updated_at = ? WHERE aid_id = ?",
        (new, float(now), str(aid_id)))
    _event(db, aid_id, new.upper(), actor, "",
           now)
    return {"aid_id": str(aid_id),
            "status": new}


def duplicates_of_db(db, *, producer_id, program,
                     item, exclude_aid=""):
    ensure_db(db)
    rows = db.query_all(
        "SELECT aid_id, status, created_at FROM"
        " agro_aid_requests WHERE producer_id = ?"
        " AND program = ? AND item = ? ORDER BY"
        " rowid", (str(producer_id),
                   str(program), str(item)))
    out = []
    for r in rows:
        if str(r["aid_id"]) == \
                str(exclude_aid):
            continue
        if str(r["status"]) in ("approved",
                                "requested"):
            out.append({
                "aid_id": str(r["aid_id"]),
                "status": str(r["status"])})
    return out


def create_request_checked_db(db, *, producer_id,
                              program, item,
                              quantity, now=0.0):
    ensure_db(db)
    dups = duplicates_of_db(
        db, producer_id=producer_id,
        program=program, item=item)
    if dups:
        raise ValueError(
            "POSIBLE DUPLICADO: ya existe "
            + str(len(dups))
            + " solicitud(es) activa(s) de "
            + str(program) + "/" + str(item)
            + " para este productor")
    aid = ("AID-"
           + uuid.uuid4().hex[:10])
    db.execute(
        "INSERT INTO agro_aid_requests (aid_id,"
        " producer_id, zid, program, item,"
        " quantity, status, eligibility,"
        " created_at, updated_at)"
        " VALUES (?, ?, NULL, ?, ?, ?,"
        " 'requested', NULL, ?, ?)",
        (aid, str(producer_id), str(program),
         str(item), _sf(quantity), float(now),
         float(now)))
    _event(db, aid, "REQUESTED", "productor",
           "", now)
    return {"aid_id": aid, "status":
            "requested",
            "duplicates_checked": True}


def impact_metrics_db(db, producer_id=None):
    ensure_db(db)
    if producer_id:
        rows = db.query_all(
            "SELECT status, COUNT(*) AS n,"
            " COALESCE(SUM(quantity), 0) AS q FROM"
            " agro_aid_requests WHERE producer_id ="
            " ? GROUP BY status",
            (str(producer_id),))
    else:
        rows = db.query_all(
            "SELECT status, COUNT(*) AS n,"
            " COALESCE(SUM(quantity), 0) AS q FROM"
            " agro_aid_requests GROUP BY status")
    by_status = {}
    for r in rows:
        by_status[str(r["status"])] = {
            "n": int(r["n"]),
            "quantity": float(r["q"])}
    approved = by_status.get("approved", {})
    total = sum(v["n"]
                for v in by_status.values())
    rate = (round(approved.get("n", 0)
                  * 100.0 / total, 2)
            if total else 0.0)
    return {"by_status": by_status,
            "total": total,
            "approval_rate_pct": rate}
