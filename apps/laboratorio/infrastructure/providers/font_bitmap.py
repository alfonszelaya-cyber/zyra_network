"""Fuente bitmap 3x5 para rasterizar texto real en PNG.

Cubre A-Z, 0-9, espacio y signos basicos. Los caracteres no
cubiertos se dibujan como bloque (declarado en metadata).
"""

G = {
    "A": (2, 5, 7, 5, 5), "B": (6, 5, 6, 5, 6), "C": (3, 4, 4, 4, 3),
    "D": (6, 5, 5, 5, 6), "E": (7, 4, 6, 4, 7), "F": (7, 4, 6, 4, 4),
    "G": (3, 4, 5, 5, 3), "H": (5, 5, 7, 5, 5), "I": (7, 2, 2, 2, 7),
    "J": (1, 1, 1, 5, 2), "K": (5, 5, 6, 5, 5), "L": (4, 4, 4, 4, 7),
    "M": (5, 7, 7, 5, 5), "N": (5, 7, 7, 7, 5), "O": (2, 5, 5, 5, 2),
    "P": (6, 5, 6, 4, 4), "Q": (2, 5, 5, 6, 3), "R": (6, 5, 6, 5, 5),
    "S": (3, 4, 2, 1, 6), "T": (7, 2, 2, 2, 2), "U": (5, 5, 5, 5, 7),
    "V": (5, 5, 5, 5, 2), "W": (5, 5, 7, 7, 5), "X": (5, 5, 2, 5, 5),
    "Y": (5, 5, 2, 2, 2), "Z": (7, 1, 2, 4, 7),
    "0": (7, 5, 5, 5, 7), "1": (2, 6, 2, 2, 7), "2": (6, 1, 2, 4, 7),
    "3": (7, 1, 2, 1, 7), "4": (5, 5, 7, 1, 1), "5": (7, 4, 6, 1, 6),
    "6": (3, 4, 7, 5, 7), "7": (7, 1, 2, 2, 2), "8": (7, 5, 2, 5, 7),
    "9": (7, 5, 7, 1, 6),
    " ": (0, 0, 0, 0, 0), "-": (0, 0, 7, 0, 0), ".": (0, 0, 0, 0, 2),
    "+": (0, 2, 7, 2, 0), "%": (5, 1, 2, 4, 5), ":": (0, 2, 0, 2, 0),
}
BLOQUE = (7, 5, 5, 5, 7)
ANCHO = 3
ALTO = 5


def glifo_de(caracter: str) -> tuple:
    """Devuelve los 5 patrones de 3 bits del caracter."""
    if not isinstance(caracter, str) or len(caracter) != 1:
        raise ValueError("glifo_de requiere un caracter.")
    c = caracter.upper()
    return G.get(c, BLOQUE)


def texto_a_lineas(texto: str) -> list:
    """Convierte texto a lista de (caracter, patrones)."""
    if not texto:
        return []
    return [(c, glifo_de(c)) for c in str(texto)[:120]]
