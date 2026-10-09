"""Alcances para integraciones entre apps (token de servicio)."""

from apps.laboratorio.constants.permissions.permission_codes import PermisoCodigo


class Alcance:
    LECTURA = "laboratorio.lectura"
    ESCRITURA = "laboratorio.escritura"
    RENDER = "laboratorio.render"
    PROYECCION = "laboratorio.proyeccion"
    GOBIERNO = "laboratorio.gobierno"
    TODOS = (LECTURA, ESCRITURA, RENDER, PROYECCION, GOBIERNO)


_MAPA = {
    Alcance.LECTURA: {PermisoCodigo.VER},
    Alcance.ESCRITURA: {
        PermisoCodigo.PROYECTO_CREAR, PermisoCodigo.PROYECTO_EDITAR,
        PermisoCodigo.CAPTURAR, PermisoCodigo.DISENAR,
        PermisoCodigo.CREAR_CONTENIDO, PermisoCodigo.EDITAR_4D,
    },
    Alcance.RENDER: {PermisoCodigo.RENDERIZAR, PermisoCodigo.EXPORTAR},
    Alcance.PROYECCION: {PermisoCodigo.PROYECTAR},
    Alcance.GOBIERNO: {PermisoCodigo.GOBIERNO_TOTAL, PermisoCodigo.RED_CONTRATOS},
}


def validar_alcance(alcance: str) -> str:
    if alcance not in Alcance.TODOS:
        raise ValueError("Alcance desconocido: " + repr(alcance))
    return alcance


def permisos_de_alcance(alcance: str) -> set:
    validar_alcance(alcance)
    return set(_MAPA[alcance])
