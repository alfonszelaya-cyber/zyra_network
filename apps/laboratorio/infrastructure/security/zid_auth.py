"""Identidad del usuario dentro de LABORATORIO (via ZYRA SuperApp)."""
from dataclasses import dataclass

from apps.laboratorio.constants.permissions.permission_codes import PermisoCodigo
from apps.laboratorio.constants.roles.role_codes import RolCodigo
from apps.laboratorio.shared.exceptions.domain_errors import PermisoDenegadoError
from apps.laboratorio.shared.policies.access_policy import PoliticaAcceso
from apps.laboratorio.validators.security.zid_validator import (
    limpiar_roles,
    validar_zid,
)

HEADER_ZID = "x-zyra-zid"
HEADER_ROLES = "x-zyra-roles"


@dataclass(frozen=True)
class Identidad:
    """Quien hace la peticion: ZID + roles + permisos derivados."""

    zid: str
    roles: tuple = ()

    @property
    def permisos(self) -> set:
        total = set()
        for rol in self.roles:
            total |= PoliticaAcceso.permisos_de(rol)
        if not total:
            total = {PermisoCodigo.VER}
        return total

    @property
    def es_gobernador(self) -> bool:
        return RolCodigo.GOBERNADOR in self.roles

    def tiene_permiso(self, codigo: str) -> bool:
        return codigo in self.permisos

    def exigir_permiso(self, codigo: str) -> None:
        if not self.tiene_permiso(codigo):
            raise PermisoDenegadoError("Permiso requerido: " + codigo)

    def tiene_rol(self, rol: str) -> bool:
        return rol in self.roles


def anonimo() -> Identidad:
    """Identidad para rutas publicas (solo lectura de estado)."""
    return Identidad(zid="anonimo", roles=())


def _buscar_header(headers: dict, nombre: str):
    if nombre in headers:
        return headers[nombre]
    for clave, valor in headers.items():
        if str(clave).lower() == nombre:
            return valor
    return None


def extraer_identidad(headers: dict, rol_defecto: str = RolCodigo.ESPECTADOR) -> Identidad:
    """Extrae y valida la identidad desde los headers del SuperApp."""
    if not isinstance(headers, dict):
        raise ValueError("Headers invalidos.")
    crudo = _buscar_header(headers, HEADER_ZID)
    if crudo is None or not str(crudo).strip():
        raise ValueError("ZID ausente en la peticion.")
    zid = validar_zid(str(crudo))
    roles = list(limpiar_roles(_buscar_header(headers, HEADER_ROLES)))
    if not roles:
        roles = [PoliticaAcceso.validar_rol(rol_defecto)]
    return Identidad(zid=zid, roles=tuple(roles))
