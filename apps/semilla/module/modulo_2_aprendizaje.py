"""Menu: Aprendizaje - SEMILLA / ZYRA (SM8)."""
MODULE = "semilla"
MENU_ID = "modulo_2_aprendizaje"
TITLE = "Aprendizaje"
OPTIONS = ["Tutor IA", "Retos adaptativos", "Mis sesiones"]


def menu() -> dict:
    """Definicion del menu (data puro)."""
    return {"module": MODULE,
            "menu_id": MENU_ID,
            "title": TITLE,
            "options": [{"key": str(i + 1),
                         "label": opt}
                        for i, opt
                        in enumerate(OPTIONS)]}
