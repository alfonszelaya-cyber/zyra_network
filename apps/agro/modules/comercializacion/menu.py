"""AGRO - navegacion del modulo comercializacion."""
MENU = {
    "key": "comercializacion",
    "title": "Comercializacion",
    "items": [{'label': 'Mercado', 'path': '/agro/mercado'}, {'label': 'Resumen', 'path': '/agro/gobierno'}],
}


def menu():
    return dict(MENU)
