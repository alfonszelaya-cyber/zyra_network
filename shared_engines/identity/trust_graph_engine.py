"""Trust Graph Engine (ID-14) - grafo de confianza
entre entidades: vinculos dirigidos con peso 0..100,
vecinos, trust_path (BFS), trust_score. Reglas 66/76."""
from __future__ import annotations
import uuid
from shared_engines.common.clocks import Clock
from shared_engines.storage.database import Database
from shared_engines.storage.migrations import (
    Migration, MigrationRunner)

_MIGRATIONS = (
    Migration(1, "zid_tg", (
        "CREATE TABLE IF NOT EXISTS zid_tg_entities ("
        " ent_id TEXT PRIMARY KEY, zid TEXT NOT NULL"
        " DEFAULT '', name TEXT NOT NULL, kind TEXT NOT"
        " NULL DEFAULT 'person', created_at REAL NOT"
        " NULL)",
        "CREATE TABLE IF NOT EXISTS zid_tg_edges ("
        " edge_id TEXT PRIMARY KEY, src TEXT NOT NULL,"
        " dst TEXT NOT NULL, relation TEXT NOT NULL"
        " DEFAULT '', weight INTEGER NOT NULL DEFAULT"
        " 50, created_at REAL NOT NULL)",
    )),
)
_KINDS = ("person", "organization", "device",
          "institution")


class TrustGraphEngine:
    """Grafo de confianza (ID-14)."""

    def __init__(self, db: Database, clock: Clock):
        self._db = db
        self._clock = clock
        MigrationRunner(db, "zid.tgraph",
                        _MIGRATIONS).run(clock)

    def add_entity(self, *, name, kind="person",
                   zid=""):
        if not str(name).strip():
            raise ValueError("name requerido")
        k = str(kind).lower()
        if k not in _KINDS:
            raise ValueError("kind debe ser "
                             + "/".join(_KINDS))
        eid = "ZTE-" + uuid.uuid4().hex[:10]
        self._db.execute(
            "INSERT INTO zid_tg_entities (ent_id,"
            " zid, name, kind, created_at)"
            " VALUES (?, ?, ?, ?, ?)",
            (eid, str(zid), str(name), k,
             self._clock.now()))
        return {"ent_id": eid}

    def link(self, *, src, dst, relation="",
             weight=50):
        for eid in (src, dst):
            row = self._db.query_one(
                "SELECT ent_id FROM zid_tg_entities"
                " WHERE ent_id = ?", (str(eid),))
            if row is None:
                raise LookupError(
                    "entidad no encontrada: "
                    + str(eid))
        if str(src) == str(dst):
            raise ValueError(
                "auto-vinculo invalido")
        w = int(weight)
        if w < 0 or w > 100:
            raise ValueError("weight 0..100")
        eid = "ZTEG-" + uuid.uuid4().hex[:10]
        self._db.execute(
            "INSERT INTO zid_tg_edges (edge_id, src,"
            " dst, relation, weight, created_at)"
            " VALUES (?, ?, ?, ?, ?, ?)",
            (eid, str(src), str(dst), str(relation),
             w, self._clock.now()))
        return {"edge_id": eid, "weight": w}

    def neighbors(self, ent_id):
        rows = self._db.query_all(
            "SELECT dst, relation, weight FROM"
            " zid_tg_edges WHERE src = ? ORDER BY"
            " rowid", (str(ent_id),))
        return [{"ent_id": str(r["dst"]),
                 "relation": str(r["relation"]),
                 "weight": int(r["weight"])}
                for r in rows]

    def trust_path(self, src, dst, max_depth=4):
        if str(src) == str(dst):
            return {"path": [str(src)],
                    "found": True}
        visited = {str(src)}
        queue = [[str(src)]]
        while queue:
            path = queue.pop(0)
            if len(path) > max_depth + 1:
                break
            last = path[-1]
            for e in self.neighbors(last):
                nxt = e["ent_id"]
                if nxt == str(dst):
                    path.append(nxt)
                    return {"path": path,
                            "found": True}
                if nxt not in visited:
                    visited.add(nxt)
                    queue.append(path + [nxt])
        return {"path": [], "found": False}

    def trust_score(self, ent_id):
        inn = self._db.query_all(
            "SELECT weight FROM zid_tg_edges WHERE"
            " dst = ?", (str(ent_id),))
        if not inn:
            return {"ent_id": str(ent_id),
                    "score": None,
                    "note": "sin vinculos"
                            " entrantes"}
        w = [int(r["weight"]) for r in inn]
        return {"ent_id": str(ent_id),
                "score": sum(w) // len(w),
                "links": len(w)}
