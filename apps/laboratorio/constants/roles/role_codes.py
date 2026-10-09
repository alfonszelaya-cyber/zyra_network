"""Roles oficiales de LABORATORIO (el menu depende del rol)."""


class RolCodigo:
    """Los 7 roles definidos en la guia maestra."""

    GOBERNADOR = "LAB_GOBERNADOR"
    CREADOR = "LAB_CREADOR"
    ANALISTA = "LAB_ANALISTA"
    OPERADOR = "LAB_OPERADOR"
    PRESENTADOR = "LAB_PRESENTADOR"
    ESPECTADOR = "LAB_ESPECTADOR"
    INTEGRADOR = "LAB_INTEGRADOR"

    TODOS = (
        GOBERNADOR, CREADOR, ANALISTA, OPERADOR,
        PRESENTADOR, ESPECTADOR, INTEGRADOR,
    )
