"""Invariante: un namespace etiquetado FUTURE no debe tener modulos con codigo."""
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def _modulos_con_codigo(ns):
    base = ROOT / "shared_engines" / ns
    total = 0
    if base.is_dir():
        for x in base.rglob("*.py"):
            if x.name == "__init__.py":
                continue
            try:
                if x.stat().st_size > 0:
                    total += 1
            except OSError:
                pass
    return total


def test_future_sin_codigo():
    man = ROOT / "NAMESPACE_MANIFEST.md"
    filas = 0
    for ln in man.read_text(encoding="utf-8").splitlines():
        s = ln.strip()
        if not (s.startswith("|") and s.count("|") >= 3):
            continue
        cells = [c.strip() for c in s.strip("|").split("|")]
        if len(cells) < 2 or not cells[0].endswith("/") or cells[0] == "Namespace":
            continue
        ns = cells[0].strip("`* ").rstrip("/")
        etiqueta = cells[1].strip("`* ").upper()
        filas += 1
        if etiqueta == "FUTURE":
            assert _modulos_con_codigo(ns) == 0, (
                ns + " etiquetado FUTURE pero tiene modulos con codigo"
            )
    assert filas >= 15, "manifiesto sin filas de namespaces: formato inesperado"
