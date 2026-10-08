
"""Land Geo Engine (A-4): GIS/parcelas sobre tierras
existentes. Coordenadas/suelo/riego/area efectiva,
uso historico por temporada, rotacion, resumen.
Patron _DDL + ensure_db (idempotente, sin reloj)."""
from __future__ import annotations
import uuid
from shared_engines.storage.database import Database

_DDL = (
    "CREATE TABLE IF NOT EXISTS agro_area_lands ("
    " land_id TEXT PRIMARY KEY, producer_id TEXT"
    " NOT NULL, location TEXT NOT NULL,"
    " size_hectares REAL NOT NULL, land_use TEXT,"
    " created_at REAL NOT NULL)",
    "CREATE TABLE IF NOT EXISTS agro_land_geo ("
    " land_id TEXT PRIMARY KEY, coordinates TEXT"
    " NOT NULL DEFAULT '', soil_type TEXT NOT NULL"
    " DEFAULT '', irrigation_access INTEGER NOT"
    " NULL DEFAULT 0, area_effective REAL,"
    " updated_at TEXT)",
    "CREATE TABLE IF NOT EXISTS agro_land_use_log ("
    " log_id INTEGER PRIMARY KEY AUTOINCREMENT,"
    " land_id TEXT NOT NULL, crop TEXT NOT NULL,"
    " season TEXT NOT NULL DEFAULT '', note TEXT"
    " NOT NULL DEFAULT '', logged_at TEXT)",
    "CREATE TABLE IF NOT EXISTS agro_land_rotations"
    " (rotation_id TEXT PRIMARY KEY, land_id TEXT"
    " NOT NULL, crop_from TEXT NOT NULL, crop_to"
    " TEXT NOT NULL, season_year TEXT NOT NULL"
    " DEFAULT '', created_at TEXT)",
)


def ensure_db(db):
    for stmt in _DDL:
        db.execute(stmt)


def _land(db, land_id):
    row = db.query_one(
        "SELECT land_id FROM agro_area_lands"
        " WHERE land_id = ?", (str(land_id),))
    if row is None:
        raise LookupError(
            "tierra no encontrada: "
            + str(land_id))
    return str(row["land_id"])


def set_geo_db(db, *, land_id, coordinates="",
               soil_type="",
               irrigation_access=False,
               area_effective=None,
               updated_at=""):
    ensure_db(db)
    _land(db, land_id)
    db.execute(
        "INSERT OR REPLACE INTO agro_land_geo"
        " (land_id, coordinates, soil_type,"
        " irrigation_access, area_effective,"
        " updated_at) VALUES (?, ?, ?, ?, ?, ?)",
        (str(land_id), str(coordinates),
         str(soil_type),
         1 if irrigation_access else 0,
         (float(area_effective)
          if area_effective is not None
          else None), str(updated_at)))
    return geo_of_db(db, land_id)


def geo_of_db(db, land_id):
    ensure_db(db)
    row = db.query_one(
        "SELECT * FROM agro_land_geo WHERE"
        " land_id = ?", (str(land_id),))
    if row is None:
        return None
    return {"land_id": str(row["land_id"]),
            "coordinates": str(
                row["coordinates"]),
            "soil_type": str(row["soil_type"]),
            "irrigation_access": bool(
                int(row["irrigation_access"])),
            "area_effective": (
                float(row["area_effective"])
                if row["area_effective"]
                is not None else None),
            "updated_at": str(
                row["updated_at"])}


def log_use_db(db, *, land_id, crop, season="",
               note="", logged_at=""):
    ensure_db(db)
    _land(db, land_id)
    db.execute(
        "INSERT INTO agro_land_use_log (land_id,"
        " crop, season, note, logged_at)"
        " VALUES (?, ?, ?, ?, ?)",
        (str(land_id), str(crop), str(season),
         str(note), str(logged_at)))
    return {"land_id": str(land_id),
            "crop": str(crop),
            "season": str(season)}


def use_log_of_db(db, land_id):
    ensure_db(db)
    rows = db.query_all(
        "SELECT crop, season, note, logged_at"
        " FROM agro_land_use_log WHERE land_id ="
        " ? ORDER BY log_id", (str(land_id),))
    return [{"crop": str(r["crop"]),
             "season": str(r["season"]),
             "note": str(r["note"]),
             "logged_at": str(r["logged_at"])}
            for r in rows]


def register_rotation_db(db, *, land_id,
                         crop_from, crop_to,
                         season_year="",
                         created_at=""):
    ensure_db(db)
    _land(db, land_id)
    rid = "ROT-" + uuid.uuid4().hex[:10]
    db.execute(
        "INSERT INTO agro_land_rotations"
        " (rotation_id, land_id, crop_from,"
        " crop_to, season_year, created_at)"
        " VALUES (?, ?, ?, ?, ?, ?)",
        (rid, str(land_id), str(crop_from),
         str(crop_to), str(season_year),
         str(created_at)))
    return {"rotation_id": rid,
            "crop_from": str(crop_from),
            "crop_to": str(crop_to)}


def rotations_of_db(db, land_id):
    ensure_db(db)
    rows = db.query_all(
        "SELECT rotation_id, crop_from, crop_to,"
        " season_year, created_at FROM"
        " agro_land_rotations WHERE land_id = ?"
        " ORDER BY rowid", (str(land_id),))
    return [{"rotation_id":
                 str(r["rotation_id"]),
             "crop_from": str(r["crop_from"]),
             "crop_to": str(r["crop_to"]),
             "season_year": str(
                 r["season_year"])}
            for r in rows]


def parcel_summary_db(db, producer_id):
    ensure_db(db)
    lands = db.query_all(
        "SELECT land_id, location, size_hectares,"
        " land_use FROM agro_area_lands WHERE"
        " producer_id = ? ORDER BY rowid",
        (str(producer_id),))
    out = []
    for r in lands:
        lid = str(r["land_id"])
        n_uses = db.query_one(
            "SELECT COUNT(*) AS n FROM"
            " agro_land_use_log WHERE land_id ="
            " ?", (lid,))
        n_rot = db.query_one(
            "SELECT COUNT(*) AS n FROM"
            " agro_land_rotations WHERE land_id"
            " = ?", (lid,))
        out.append({"land_id": lid,
                    "location": str(
                        r["location"]),
                    "size_hectares": float(
                        r["size_hectares"]),
                    "land_use": (
                        str(r["land_use"])
                        if r["land_use"]
                        is not None else ""),
                    "geo": geo_of_db(db, lid),
                    "uses": int(n_uses["n"]),
                    "rotations": int(
                        n_rot["n"])})
    return {"producer_id": str(producer_id),
            "parcels": out,
            "total": len(out)}
