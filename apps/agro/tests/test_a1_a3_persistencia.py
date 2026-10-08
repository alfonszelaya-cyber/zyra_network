import dataclasses
import inspect as _insp
import pathlib
import pytest
from shared_engines.common.clocks import FrozenClock
from shared_engines.storage.database import SQLiteAdapter
from apps.agro.infrastructure.database.repository import InMemoryRepository
from apps.agro.infrastructure.repositories.sqlite_repository import (
    SqliteProducerRepository,
    SqliteProductionRepository,
    migrate_from_memory)


class _Ent:
    """Imita las entidades reales del InMemoryRepository
    (objetos con .id)."""

    def __init__(self, eid, data):
        self.id = eid
        self.data = data


def test_a1_producer_persistencia_real(tmp_path) -> None:
    db = SQLiteAdapter(tmp_path / "p.db")
    repo = SqliteProducerRepository(db, FrozenClock())
    e1 = repo.save({"producer_id": "PR-1",
                    "name": "Juan",
                    "hectares": 12.5})
    assert e1["entity_id"] == "PR-1"
    assert e1["name"] == "Juan"
    got = repo.get("PR-1")
    assert got is not None
    assert got["hectares"] == 12.5
    repo.save({"producer_id": "PR-2",
               "name": "Maria"})
    assert repo.count() == 2
    assert len(repo.list()) == 2
    upd = repo.save({"producer_id": "PR-1",
                     "name": "Juan Perez"})
    assert upd["name"] == "Juan Perez"
    assert repo.count() == 2
    assert repo.delete("PR-2") is True
    assert repo.delete("PR-2") is False
    assert repo.get("PR-2") is None
    db2 = SQLiteAdapter(tmp_path / "p.db")
    repo2 = SqliteProducerRepository(db2,
                                     FrozenClock())
    assert repo2.count() == 1
    assert repo2.get("PR-1")["name"] == "Juan Perez"
    print("OK A-1 producer: save/get/list/update/delete contra SQLite REAL + sobrevive reinicio de conexion")


def test_a1_migration_desde_memoria(tmp_path) -> None:
    mem = InMemoryRepository()
    mem.save(_Ent("X-1", "algo"))
    mem.save(_Ent("X-2", "otro"))
    db = SQLiteAdapter(tmp_path / "m.db")
    dst = SqliteProductionRepository(db,
                                     FrozenClock())
    n = migrate_from_memory(mem, dst)
    assert n == 2
    assert dst.count() == 2
    got = dst.get("X-1")
    assert got["data"] == "algo"
    n2 = migrate_from_memory(mem, dst)
    assert n2 == 2
    assert dst.count() == 2
    print("OK A-1: migracion memoria->SQLite idempotente con entidades OBJETO (.id) como el InMemoryRepository real; interfaz IDENTICA (regla 51)")


def test_a3_utcnow_eliminado(tmp_path) -> None:
    root = pathlib.Path("apps/agro")
    offenders = []
    for f in root.rglob("*.py"):
        if ("__pycache__" in f.parts
                or "tests" in f.parts):
            continue
        try:
            t = f.read_text(encoding="utf-8")
        except Exception:
            continue
        if ("datetime.utcnow()" in t
                or "default_factory="
                "datetime.utcnow" in t):
            offenders.append(str(f))
    assert offenders == []
    from apps.agro.domain.entities import \
        base_entity as be
    from apps.agro.domain.events import \
        domain_event as de
    s1 = _insp.getsource(be)
    s2 = _insp.getsource(de)
    assert "utcnow" not in s1
    assert "utcnow" not in s2
    assert "datetime.now(timezone.utc)" in s1
    assert ("default_factory=lambda: datetime"
            ".now(timezone.utc)") in s1
    dcs = [o for o in vars(be).values()
           if dataclasses.is_dataclass(o)]
    found_tz = False
    for dc in dcs:
        for fd in dataclasses.fields(dc):
            fct = fd.default_factory
            if fct is dataclasses.MISSING:
                continue
            if not callable(fct):
                continue
            try:
                v = fct()
            except Exception:
                continue
            if getattr(v, "tzinfo",
                       None) is not None:
                found_tz = True
    assert found_tz is True
    print("OK A-3: cero utcnow en produccion (ambos patrones) + factories TZ-AWARE verificados")
