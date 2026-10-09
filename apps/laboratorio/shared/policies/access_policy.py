"""Politica de acceso: mapa oficial rol -> permisos."""
from apps.laboratorio.constants.permissions.permission_codes import PermisoCodigo
from apps.laboratorio.constants.roles.role_codes import RolCodigo

PERMISOS_POR_ROL = {
    RolCodigo.GOBERNADOR: set(PermisoCodigo.TODOS),
    RolCodigo.CREADOR: {
        PermisoCodigo.VER, PermisoCodigo.PROYECTO_CREAR, PermisoCodigo.PROYECTO_EDITAR,
        PermisoCodigo.CAPTURAR, PermisoCodigo.DISENAR, PermisoCodigo.CREAR_CONTENIDO,
        PermisoCodigo.EDITAR_4D, PermisoCodigo.BIBLIOTECA_GESTIONAR,
    },
    RolCodigo.ANALISTA: {
        PermisoCodigo.VER, PermisoCodigo.SIMULAR, PermisoCodigo.EVALUAR,
        PermisoCodigo.COMPARAR, PermisoCodigo.OPTIMIZAR, PermisoCodigo.RENDERIZAR,
    },
    RolCodigo.OPERADOR: {PermisoCodigo.VER, PermisoCodigo.PROYECTAR},
    RolCodigo.PRESENTADOR: {PermisoCodigo.VER, PermisoCodigo.PRESENTAR, PermisoCodigo.EXPORTAR},
    RolCodigo.ESPECTADOR: {PermisoCodigo.VER},
    RolCodigo.INTEGRADOR: {PermisoCodigo.VER, PermisoCodigo.RED_CONTRATOS},
}


class PoliticaAcceso:
    """Dueña unica del mapa rol-permisos del menu por rol."""

    @staticmethod
    def permisos_de(rol: str) -> set:
        """Devuelve el set de permisos del rol; falla si es desconocido."""
        if rol not in PERMISOS_POR_ROL:
            raise ValueError("Rol desconocido: " + repr(rol))
        return set(PERMISOS_POR_ROL[rol])

    @staticmethod
    def tiene_permiso(rol: str, codigo: str) -> bool:
        """True si el rol concede el codigo de permiso."""
        return codigo in PoliticaAcceso.permisos_de(rol)

    @staticmethod
    def validar_rol(rol: str) -> str:
        """Valida y devuelve el rol si existe en el mapa oficial."""
        PoliticaAcceso.permisos_de(rol)
        return rol
