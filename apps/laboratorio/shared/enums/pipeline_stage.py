"""Cadena de creacion D1: las 20 etapas oficiales en orden exacto."""

from enum import Enum


class PipelineStage(str, Enum):
    """Orden oficial e inmutable de la cadena de LABORATORIO."""

    DESCRIBIR = "describir"
    FOTOGRAFIAR = "fotografiar"
    ESCANEAR = "escanear"
    MEDIR = "medir"
    IMPORTAR = "importar"
    COMPRENDER = "comprender"
    DISENAR = "disenar"
    CREAR = "crear"
    SIMULAR = "simular"
    PROBAR = "probar"
    COMPARAR = "comparar"
    OPTIMIZAR = "optimizar"
    TRES_D = "3d"
    CUATRO_D = "4d"
    FOTORREALISMO = "fotorrealismo"
    PRESENTACION = "presentacion"
    PROYECCION = "proyeccion"
    LIGHT_FIELD = "light_field"
    HOLOGRAFIA = "holografia"
    AR_VR = "ar_vr"

    @classmethod
    def cadena_completa(cls) -> list:
        """Devuelve la cadena D1 completa en su orden oficial."""
        return [etapa.value for etapa in cls]

    @classmethod
    def validar(cls, valor: str) -> "PipelineStage":
        """Convierte y valida un texto a PipelineStage."""
        if not isinstance(valor, str):
            raise ValueError("La etapa debe ser texto.")
        limpio = valor.strip().lower()
        try:
            return cls(limpio)
        except ValueError:
            validos = ", ".join(t.value for t in cls)
            raise ValueError(
                "Etapa invalida: " + repr(valor) + ". Validas: " + validos
            )
