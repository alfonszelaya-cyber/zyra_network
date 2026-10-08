
"""Livestock Engine (A-7): ganaderia completa —
expediente por animal con genealogia sire/dam
verificada, eventos VACUNA/TRATAMIENTO/PESO/
MOVIMIENTO/MUERTE (muerte bloquea posteriores,
regla 66), resumen vivos/muertos por especie.
Patron _DDL + ensure_db."""
from __future__ import annotations
import uuid
from shared_engines.storage.database import Database

_DDL = (
    "CREATE TABLE IF NOT EXISTS agro_animals ("
    " animal_id TEXT PRIMARY KEY, producer_id TEXT"
    " NOT NULL, species TEXT NOT NULL, breed TEXT"
    " NOT NULL DEFAULT '', birth_date TEXT NOT"
    " NULL DEFAULT '', sire_id TEXT NOT NULL"
    " DEFAULT '', dam_id TEXT NOT NULL DEFAULT '',"
    " status TEXT NOT NULL DEFAULT 'vivo',"
    " created_at TEXT)",
    "CREATE TABLE IF NOT EXISTS"
    " agro_animal_events (event_id TEXT PRIMARY"
    " KEY, animal_id TEXT NOT NULL, kind TEXT NOT"
    " NULL, detail TEXT NOT NULL DEFAULT '', value"
    " REAL, event_date TEXT NOT NULL DEFAULT '',"
    " created_at TEXT)",
)
_EVENTS = ("VACUNA", "TRATAMIENTO", "PESO",
           "MOVIMIENTO", "MUERTE")


def ensure_db(db):
    for stmt in _DDL:
        db.execute(stmt)


def _animal(db, animal_id):
    row = db.query_one(
        "SELECT animal_id, status FROM"
        " agro_animals WHERE animal_id = ?",
        (str(animal_id),))
    if row is None:
        raise LookupError(
            "animal no encontrado: "
            + str(animal_id))
    return row


def register_animal_db(db, *, producer_id,
                       species, breed="",
                       birth_date="", sire_id="",
                       dam_id="", created_at=""):
    ensure_db(db)
    if not str(species).strip():
        raise ValueError("species requerida")
    for pid_val in (sire_id, dam_id):
        if str(pid_val).strip():
            parent = db.query_one(
                "SELECT animal_id FROM"
                " agro_animals WHERE animal_id ="
                " ?", (str(pid_val),))
            if parent is None:
                raise LookupError(
                    "progenitor no encontrado: "
                    + str(pid_val))
    aid = "ANM-" + uuid.uuid4().hex[:10]
    db.execute(
        "INSERT INTO agro_animals (animal_id,"
        " producer_id, species, breed, birth_date,"
        " sire_id, dam_id, status, created_at)"
        " VALUES (?, ?, ?, ?, ?, ?, ?, 'vivo', ?)",
        (aid, str(producer_id), str(species),
         str(breed), str(birth_date),
         str(sire_id), str(dam_id),
         str(created_at)))
    return {"animal_id": aid,
            "species": str(species),
            "status": "vivo"}


def animal_of_db(db, animal_id):
    ensure_db(db)
    row = db.query_one(
        "SELECT * FROM agro_animals WHERE animal_id"
        " = ?", (str(animal_id),))
    if row is None:
        return None
    return {"animal_id": str(row["animal_id"]),
            "producer_id": str(
                row["producer_id"]),
            "species": str(row["species"]),
            "breed": str(row["breed"]),
            "birth_date": str(row["birth_date"]),
            "sire_id": str(row["sire_id"]),
            "dam_id": str(row["dam_id"]),
            "status": str(row["status"])}


def animals_of_db(db, producer_id, status=""):
    ensure_db(db)
    if str(status).strip():
        rows = db.query_all(
            "SELECT animal_id, species, breed,"
            " status FROM agro_animals WHERE"
            " producer_id = ? AND status = ?"
            " ORDER BY rowid",
            (str(producer_id), str(status)))
    else:
        rows = db.query_all(
            "SELECT animal_id, species, breed,"
            " status FROM agro_animals WHERE"
            " producer_id = ? ORDER BY rowid",
            (str(producer_id),))
    return [{"animal_id": str(r["animal_id"]),
             "species": str(r["species"]),
             "breed": str(r["breed"]),
             "status": str(r["status"])}
            for r in rows]


def add_event_db(db, *, animal_id, kind,
                 detail="", value=None,
                 event_date="", created_at=""):
    ensure_db(db)
    row = _animal(db, animal_id)
    k = str(kind).upper()
    if k not in _EVENTS:
        raise ValueError("kind debe ser "
                         + "/".join(_EVENTS))
    if str(row["status"]) == "muerto":
        raise ValueError(
            "animal MUERTO: sin eventos"
            " posteriores (regla 66)")
    eid = "ANEV-" + uuid.uuid4().hex[:10]
    db.execute(
        "INSERT INTO agro_animal_events (event_id,"
        " animal_id, kind, detail, value,"
        " event_date, created_at)"
        " VALUES (?, ?, ?, ?, ?, ?, ?)",
        (eid, str(animal_id), k, str(detail),
         (float(value) if value is not None
          else None), str(event_date),
         str(created_at)))
    if k == "MUERTE":
        db.execute(
            "UPDATE agro_animals SET status ="
            " 'muerto' WHERE animal_id = ?",
            (str(animal_id),))
    return {"event_id": eid, "kind": k,
            "value": (float(value)
                      if value is not None
                      else None)}


def events_of_db(db, animal_id):
    ensure_db(db)
    rows = db.query_all(
        "SELECT event_id, kind, detail, value,"
        " event_date FROM agro_animal_events WHERE"
        " animal_id = ? ORDER BY rowid",
        (str(animal_id),))
    return [{"event_id": str(r["event_id"]),
             "kind": str(r["kind"]),
             "detail": str(r["detail"]),
             "value": (float(r["value"])
                       if r["value"] is not None
                       else None),
             "event_date": str(
                 r["event_date"])}
            for r in rows]


def genealogy_of_db(db, animal_id):
    ensure_db(db)
    row = _animal(db, animal_id)
    out = {"animal_id": str(animal_id)}
    row_full = db.query_one(
        "SELECT sire_id, dam_id FROM agro_animals"
        " WHERE animal_id = ?",
        (str(animal_id),))
    for name, col in (("sire", "sire_id"),
                      ("dam", "dam_id")):
        pid = str(row_full[col])
        parent = None
        if pid:
            p = db.query_one(
                "SELECT animal_id, species, breed,"
                " status FROM agro_animals WHERE"
                " animal_id = ?", (pid,))
            if p is not None:
                parent = {
                    "animal_id": str(
                        p["animal_id"]),
                    "species": str(p["species"]),
                    "breed": str(p["breed"]),
                    "status": str(p["status"])}
        out[name] = parent
    return out


def livestock_summary_db(db, producer_id):
    ensure_db(db)
    rows = db.query_all(
        "SELECT species, status, COUNT(*) AS n"
        " FROM agro_animals WHERE producer_id = ?"
        " GROUP BY species, status ORDER BY"
        " species, status", (str(producer_id),))
    by_species = {}
    for r in rows:
        sp = str(r["species"])
        e = by_species.setdefault(
            sp, {"vivos": 0, "muertos": 0})
        if str(r["status"]) == "muerto":
            e["muertos"] += int(r["n"])
        else:
            e["vivos"] += int(r["n"])
    n_ev = db.query_one(
        "SELECT COUNT(*) AS n FROM"
        " agro_animal_events ae JOIN agro_animals"
        " a ON ae.animal_id = a.animal_id WHERE"
        " a.producer_id = ?", (str(producer_id),))
    return {"producer_id": str(producer_id),
            "by_species": by_species,
            "events": int(n_ev["n"])}
