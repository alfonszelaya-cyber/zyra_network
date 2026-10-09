"""Validaciones comunes reutilizables en toda la aplicacion."""


def exigir_texto(valor, nombre_campo: str, minimo: int = 1, maximo: int = 5000) -> str:
    """Valida texto no vacio dentro de limites; lo devuelve limpio."""
    if not isinstance(valor, str):
        raise ValueError(nombre_campo + " debe ser texto.")
    limpio = valor.strip()
    if len(limpio) < minimo:
        raise ValueError(
            nombre_campo + " debe tener al menos " + str(minimo) + " caracteres."
        )
    if len(limpio) > maximo:
        raise ValueError(
            nombre_campo + " no puede exceder " + str(maximo) + " caracteres."
        )
    return limpio


def exigir_entero(
    valor, nombre_campo: str, minimo: int = 0, maximo: int = 1000000
) -> int:
    """Valida que sea entero dentro de rango; lo devuelve."""
    if isinstance(valor, bool) or not isinstance(valor, int):
        raise ValueError(nombre_campo + " debe ser un numero entero.")
    if valor < minimo or valor > maximo:
        raise ValueError(
            nombre_campo + " fuera de rango: "
            + str(minimo) + " a " + str(maximo) + "."
        )
    return valor


def exigir_flotante(
    valor, nombre_campo: str, minimo: float = 0.0, maximo: float = 1e12
) -> float:
    """Valida que sea numero real dentro de rango; lo devuelve."""
    if isinstance(valor, bool) or not isinstance(valor, (int, float)):
        raise ValueError(nombre_campo + " debe ser un numero.")
    numero = float(valor)
    if numero < minimo or numero > maximo:
        raise ValueError(
            nombre_campo + " fuera de rango: "
            + str(minimo) + " a " + str(maximo) + "."
        )
    return numero


def limpiar_texto_multilinea(valor, nombre_campo: str, maximo: int = 20000) -> str:
    """Normaliza un texto largo de varias lineas."""
    if not isinstance(valor, str):
        raise ValueError(nombre_campo + " debe ser texto.")
    normalizado = "\n".join(
        linea.rstrip() for linea in valor.strip().splitlines()
    )
    if not normalizado:
        raise ValueError(nombre_campo + " no puede estar vacio.")
    if len(normalizado) > maximo:
        raise ValueError(
            nombre_campo + " excede el maximo de " + str(maximo) + " caracteres."
        )
    return normalizado
