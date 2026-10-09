"""Los 11 tipos de creacion oficiales de LABORATORIO."""

from enum import Enum


class CreationType(str, Enum):
    """Dominios de creacion: todo proyecto nace con UN tipo oficial."""

    PRESENTACION = "presentacion"
    ARQUITECTURA = "arquitectura"
    NEGOCIO = "negocio"
    LEY = "ley"
    APP = "app"
    AGRO = "agro"
    EMPLEO = "empleo"
    INFRAESTRUCTURA = "infraestructura"
    EDUCACION = "educacion"
    PRODUCTO = "producto"
    GOBIERNO = "gobierno"

    @classmethod
    def validar(cls, valor: str) -> "CreationType":
        """Convierte y valida un texto a CreationType."""
        if not isinstance(valor, str):
            raise ValueError("El tipo de creacion debe ser texto.")
        limpio = valor.strip().lower()
        try:
            return cls(limpio)
        except ValueError:
            validos = ", ".join(t.value for t in cls)
            raise ValueError(
                "Tipo de creacion invalido: " + repr(valor)
                + ". Validos: " + validos
            )
