"""Menu: Futuro Profesional - SEMILLA / ZYRA (SM8)."""
MODULE = "semilla"
MENU_ID = "modulo_9_futuro_profesional"
TITLE = "Futuro Profesional"
OPTIONS = ["Orientacion vocacional", "Rutas avanzadas"]


def menu() -> dict:
    """Definicion del menu (data puro)."""
    return {"module": MODULE,
            "menu_id": MENU_ID,
            "title": TITLE,
            "options": [{"key": str(i + 1),
                         "label": opt}
                        for i, opt
                        in enumerate(OPTIONS)]}
