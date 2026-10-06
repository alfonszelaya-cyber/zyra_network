import importlib, pathlib, pytest

BASE = pathlib.Path(__file__).resolve().parents[1] / "application"

def test_import_todos_los_use_cases():
    n = 0
    errores = []
    for p in sorted(BASE.rglob("*.py")):
        if p.stat().st_size <= 1:
            continue
        rel = ("apps.nexo."
               + p.relative_to(BASE.parent)
               .as_posix()[:-3].replace("/", "."))
        try:
            importlib.import_module(rel)
            n = n + 1
        except Exception as e:
            errores.append(rel + ": " + str(e)[:80])
    assert errores == []
    assert n >= 50
    print("OK use cases: " + str(n) + " importan sin errores")

def test_idempotencia_claim_complete(tmp_path):
    from shared_engines.common.clocks import FrozenClock
    from shared_engines.storage.database import SQLiteAdapter
    from apps.nexo.domain.operations.idempotency_engine import IdempotencyEngine
    eng = IdempotencyEngine(
        SQLiteAdapter(tmp_path / "idem.db"), FrozenClock())
    c1 = eng.claim(key="op-1", scope="pagos")
    assert c1["first"] is True
    eng.complete(key="op-1", scope="pagos",
                 result={"ok": True})
    c2 = eng.claim(key="op-1", scope="pagos")
    assert c2["first"] is False
    assert c2["result"] == {"ok": True}
    assert eng.claim(key="op-2",
                     scope="pagos")["first"] is True
    eng.forget(key="op-1", scope="pagos")
    assert eng.claim(key="op-1",
                     scope="pagos")["first"] is True
    print("OK idempotencia: claim/complete/replay/forget")
