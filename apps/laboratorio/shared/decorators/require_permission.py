"""Decorador de permisos: exige un codigo antes de ejecutar."""
import functools

from apps.laboratorio.shared.exceptions.domain_errors import PermisoDenegadoError


def requiere_permiso(verificador, codigo_permiso: str):
    """Fábrica: verificador(codigo) -> bool concede o deniega."""

    if not callable(verificador):
        raise ValueError("El verificador debe ser callable.")
    if not codigo_permiso or not isinstance(codigo_permiso, str):
        raise ValueError("Codigo de permiso invalido.")

    def decorador(func):
        @functools.wraps(func)
        def wrapper(*args, **kwargs):
            if not verificador(codigo_permiso):
                raise PermisoDenegadoError(
                    "Permiso requerido: " + codigo_permiso
                )
            return func(*args, **kwargs)

        return wrapper

    return decorador
