"""Fase del plan aprobado en la que vive cada menu (Ley 1: honesto).

Un menu con fase mayor a 1 declara que su backend llega en esa fase;
la UI lo muestra y sus botones aparecen deshabilitados con motivo.
"""

FASE_POR_MENU = {
    "inicio": 1,
    "simular": 1,
    "capturar": 2,
    "comprender": 2,
    "disenar": 2,
    "biblioteca": 3,
    "crear": 3,
    "cuatro_d": 4,
    "probar": 5,
    "comparar": 5,
    "optimizar": 5,
    "renderizar": 6,
    "presentar": 7,
    "exportar": 7,
    "proyectar": 8,
    "salidas": 8,
    "red": 9,
    "gobierno": 10,
}
