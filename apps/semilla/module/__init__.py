
"""Menu Registry de modulos SEMILLA (SM8)."""
from pathlib import Path
import importlib

_BASE = Path(__file__).parent

def discover_menus() -> list:
    """Descubre los menu.py con contenido."""
    menus = []
    for p in sorted(_BASE.rglob("*.py")):
        try:
            if p.name == "__init__.py":
                continue
            if p.stat().st_size <= 1:
                continue
            rel = p.relative_to(_BASE).as_posix()
            mod = importlib.import_module(
                "apps.semilla.module."
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
