"""Reglas atomicas de acceso reutilizables por politicas y handlers."""

from apps.laboratorio.constants.roles.role_codes import RolCodigo


def es_propietario(entidad, zid: str) -> bool:
    if entidad is None or not zid:
        return False
    return getattr(entidad, "propietario_zid", "") == zid


def tiene_rol(identidad, rol: str) -> bool:
    return identidad is not None and rol in getattr(identidad, "roles", ())


def puede_gobernar(identidad) -> bool:
    return tiene_rol(identidad, RolCodigo.GOBERNADOR)
