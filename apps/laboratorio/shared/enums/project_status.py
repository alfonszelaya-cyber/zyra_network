"""Estados del ciclo de vida de un proyecto de LABORATORIO."""

from enum import Enum


class ProjectStatus(str, Enum):
    """Ciclo de vida: todo proyecto esta exactamente en UN estado."""

    BORRADOR = "borrador"
    EN_COMPRESION = "en_compresion"
    EN_DISENO = "en_diseno"
    EN_CREACION = "en_creacion"
    EN_SIMULACION = "en_simulacion"
    EN_RENDER = "en_render"
    EN_PRESENTACION = "en_presentacion"
    EN_PROYECCION = "en_proyeccion"
    ENTREGADO = "entregado"
    ARCHIVADO = "archivado"
