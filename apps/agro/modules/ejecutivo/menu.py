"""AGRO - navegacion del modulo ejecutivo."""
MENU = {
    "key": "ejecutivo",
    "title": "Ejecutivo",
    "items": [{'label': 'Resumen general', 'path': '/agro/gobierno'}],
}


def menu():
    return dict(MENU)
