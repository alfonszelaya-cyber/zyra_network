
"""Menu Registry de modulos NEXO (NG10).

Descubre los menu.py con contenido de los modulos.
Regla 70: operaciones/logistica EXCLUIDO (SUBASTAS).
Archivos vacios se saltan (regla 53/68)."""
from pathlib import Path
import importlib

_BASE = Path(__file__).parent
_EXCLUDED = ("operaciones/logistica",)

def discover_menus() -> list:
    """Descubre y devuelve todos los menus."""
    menus = []
    for p in sorted(_BASE.rglob("menu.py")):
        try:
            if p.stat().st_size <= 1:
                continue
            rel = p.relative_to(
                _BASE).as_posix()
            if any(rel.startswith(x)
                   for x in _EXCLUDED):
                continue
            mod = importlib.import_module(
                "apps.nexo.module."
                + rel[:-3].replace("/", "."))
            fn = getattr(mod, "menu", None)
            if not callable(fn):
                continue
            entry = fn()
            entry["path"] = rel
            menus.append(entry)
        except Exception:
            continue
    return menus
