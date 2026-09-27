"""AGRO - navegacion del modulo produccion."""
MENU = {
    "key": "produccion",
    "title": "Produccion",
    "items": [{'label': 'Produccion nacional', 'path': '/agro/gobierno/seguridad'}, {'label': 'Registrar cosecha', 'path': '/agro'}],
}


def menu():
    return dict(MENU)
