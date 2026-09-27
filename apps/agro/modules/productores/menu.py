"""AGRO - navegacion del modulo productores."""
MENU = {
    "key": "productores",
    "title": "Productores",
    "items": [{'label': 'Registro', 'path': '/agro'}, {'label': 'Padron', 'path': '/agro/gobierno'}],
}


def menu():
    return dict(MENU)
