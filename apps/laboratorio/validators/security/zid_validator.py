"""Validacion del ZID y roles recibidos desde ZYRA SuperApp."""
import re
from apps.laboratorio.constants.roles.role_codes import RolCodigo

PATRON_ZID = re.compile(r"^[A-Za-z0-9][A-Za-z0-9_.-]{2,63}$")


def validar_zid(valor) -> str:
    """Valida formato de ZID y lo devuelve limpio."""
    if not isinstance(valor, str):
        raise ValueError("El ZID debe ser texto.")
    limpio = valor.strip()
    if not PATRON_ZID.match(limpio):
        raise ValueError("Formato de ZID invalido: " + repr(valor))
    return limpio


def limpiar_roles(texto) -> tuple:
    """Separa roles por coma; ignora los no reconocidos."""
    if texto is None or (isinstance(texto, str) and not texto.strip()):
        return ()
    if not isinstance(texto, str):
        raise ValueError("Los roles deben venir como texto separado por comas.")
    roles = []
    for parte in texto.split(","):
        rol = parte.strip()
        if rol and rol in RolCodigo.TODOS and rol not in roles:
            roles.append(rol)
    return tuple(roles)
