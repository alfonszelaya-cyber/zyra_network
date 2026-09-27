"""AGRO - navegacion del modulo atencion_al_cliente."""
MENU = {
    "key": "atencion_al_cliente",
    "title": "Atencion al Cliente",
    "items": [{'label': 'Inicio', 'path': '/agro'}, {'label': 'Soporte del Gobierno', 'path': '/agro/gobierno'}],
}


def menu():
    return dict(MENU)
