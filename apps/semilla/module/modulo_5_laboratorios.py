"""Menu: Laboratorios - SEMILLA / ZYRA (SM8)."""
MODULE = "semilla"
MENU_ID = "modulo_5_laboratorios"
TITLE = "Laboratorios"
OPTIONS = ["Proyectos de lab", "Experimentos", "Resultados"]


def menu() -> dict:
    """Definicion del menu (data puro)."""
    return {"module": MODULE,
            "menu_id": MENU_ID,
            "title": TITLE,
            "options": [{"key": str(i + 1),
                         "label": opt}
                        for i, opt
                        in enumerate(OPTIONS)]}
