import importlib, pathlib

BASE = pathlib.Path(__file__).resolve().parents[1] / "module"

def test_modulos_legacy_importan():
    n = 0
    for p in sorted(BASE.glob("modulo_*.py")):
        if p.stat().st_size <= 1:
            continue
        importlib.import_module(
            "apps.nexo.module." + p.stem)
        n = n + 1
    assert n >= 5
    print("OK modules: " + str(n)
          + " modulos legacy importan")
