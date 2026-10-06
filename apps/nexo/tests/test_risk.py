import importlib, pathlib

BASE = pathlib.Path(__file__).resolve().parents[1] / "domain" / "risk"

def test_modulos_riesgo_importan():
    n = 0
    errores = []
    for p in sorted(BASE.glob("*.py")):
        if p.stat().st_size <= 1:
            continue
        try:
            importlib.import_module(
                "apps.nexo.domain.risk." + p.stem)
            n = n + 1
        except Exception as e:
            errores.append(p.stem + ": " + str(e)[:80])
    assert errores == []
    assert n >= 10
    print("OK risk: " + str(n)
          + " modulos importan sin errores")
