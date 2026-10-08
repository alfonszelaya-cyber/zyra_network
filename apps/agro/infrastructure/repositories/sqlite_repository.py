
"""SqliteRepository (A-1) - persistencia REAL
para AGRO con la MISMA interfaz del repositorio
en memoria (save/get/list/delete).

v3 (fix): self._clock = clock RESTAURADO en
__init__ (v2 lo perdio al reordenar; save()
lanzaba AttributeError).
v2: migraciones con tupla explicita
(migs = (Migration(...),) — coma DENTRO).
_key acepta dicts (entity_id/id/producer_id/
production_id) y objetos con atributos (.id,
como el InMemoryRepository real).
Regla 76: ORDER BY rowid."""
from __future__ import annotations
import json as _j
import uuid
from shared_engines.storage.database import (
    Database)
from shared_engines.storage.migrations import (
    Migration, MigrationRunner)


class SqliteRepository:
    """Repositorio SQLite generico (A-1)."""

    ENTITY = "generic"

    def __init__(self, db, clock=None):
        self._db = db
        self._clock = clock
        table = self._table()
        stmt = ("CREATE TABLE IF NOT EXISTS "
                + table
                + " (entity_id TEXT PRIMARY KEY,"
                " payload_json TEXT NOT NULL,"
                " created_at REAL NOT NULL,"
                " updated_at REAL NOT NULL)")
        migs = (Migration(1, table,
                          (stmt,)),)
        MigrationRunner(
            db,
            "agro.repo." + self.ENTITY,
            migs).run(clock)

    @classmethod
    def _table(cls) -> str:
        return ("agro_"
                + cls.ENTITY
                + "_entities")

    @staticmethod
    def _key(entity) -> str:
        if isinstance(entity, dict):
            for k in ("entity_id", "id",
                      "producer_id",
                      "production_id"):
                v = entity.get(k)
                if v:
                    return str(v)
            new = ("AGR-"
                   + uuid.uuid4().hex[:12])
            entity["entity_id"] = new
            return new
        new = None
        for attr in ("entity_id", "id",
                     "producer_id",
                     "production_id"):
            v = getattr(entity, attr, None)
            if v:
                new = str(v)
                break
        if not new:
            new = ("AGR-"
                   + uuid.uuid4().hex[:12])
        try:
            if not getattr(entity,
                           "entity_id", None):
                setattr(entity, "entity_id",
                        new)
        except Exception:
            pass
        return new

    def save(self, entity):
        k = self._key(entity)
        now = 0.0
        if self._clock is not None:
            now = self._clock.now()
        payload = _j.dumps(
            entity if isinstance(entity, dict)
            else getattr(entity, "__dict__",
                         {}),
            default=str, sort_keys=True)
        self._db.execute(
            "INSERT OR REPLACE INTO "
            + self._table()
            + " (entity_id, payload_json,"
              " created_at, updated_at)"
              " VALUES (?, ?,"
              " COALESCE((SELECT created_at"
              " FROM " + self._table()
              + " WHERE entity_id = ?), ?),"
              " ?)",
            (k, payload, k, now, now))
        return self.get(k)

    def get(self, entity_id):
        row = self._db.query_one(
            "SELECT payload_json FROM "
            + self._table()
            + " WHERE entity_id = ?",
            (str(entity_id),))
        if not row:
            return None
        d = _j.loads(str(row["payload_json"]))
        if isinstance(d, dict):
            d.setdefault("entity_id",
                         str(entity_id))
        return d

    def list(self):
        rows = self._db.query_all(
            "SELECT payload_json, entity_id"
            " FROM " + self._table()
            + " ORDER BY rowid")
        out = []
        for r in rows:
            d = _j.loads(
                str(r["payload_json"]))
            if isinstance(d, dict):
                d.setdefault(
                    "entity_id",
                    str(r["entity_id"]))
            out.append(d)
        return out

    def delete(self, entity_id) -> bool:
        row = self._db.query_one(
            "SELECT entity_id FROM "
            + self._table()
            + " WHERE entity_id = ?",
            (str(entity_id),))
        if not row:
            return False
        self._db.execute(
            "DELETE FROM " + self._table()
            + " WHERE entity_id = ?",
            (str(entity_id),))
        return True

    def count(self) -> int:
        row = self._db.query_one(
            "SELECT COUNT(*) AS n FROM "
            + self._table())
        return int(row["n"]) if row else 0


class SqliteProducerRepository(SqliteRepository):
    ENTITY = "producer"


class SqliteProductionRepository(
        SqliteRepository):
    ENTITY = "production"


def migrate_from_memory(src, dst) -> int:
    """Copia entidades del repo en memoria al
    SQLite (regla 51). Robusto con list() y
    _items.values()."""
    n = 0
    items = list(src.list() or [])
    if items and not any(
            isinstance(e, dict)
            or hasattr(e, "__dict__")
            for e in items):
        items = list(getattr(
            src, "_items", {}).values())
    for e in items:
        if (isinstance(e, dict)
                or hasattr(e, "__dict__")):
            dst.save(e)
            n += 1
    return n
