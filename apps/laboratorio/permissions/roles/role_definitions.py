"""Definiciones oficiales de roles: menus visibles por rol."""

from apps.laboratorio.constants.roles.role_codes import RolCodigo

DEFINICIONES = {
    RolCodigo.GOBERNADOR: {
        "nombre": "Gobernador",
        "descripcion": "Control total de LABORATORIO",
        "menus": ("inicio", "capturar", "comprender", "disenar", "crear", "cuatro_d", "simular", "probar", "comparar", "optimizar", "renderizar", "presentar", "proyectar", "salidas", "exportar", "biblioteca", "red", "gobierno"),
    },
    RolCodigo.CREADOR: {
        "nombre": "Creador",
        "descripcion": "Captura, comprension, diseno y creacion 4D",
        "menus": ("inicio", "capturar", "comprender", "disenar", "crear", "cuatro_d", "biblioteca"),
    },
    RolCodigo.ANALISTA: {
        "nombre": "Analista",
        "descripcion": "Simulacion, evaluacion, comparacion y render",
        "menus": ("inicio", "simular", "probar", "comparar", "optimizar", "renderizar"),
    },
    RolCodigo.OPERADOR: {
        "nombre": "Operador",
        "descripcion": "Proyeccion en superficies y salidas",
        "menus": ("inicio", "proyectar", "salidas"),
    },
    RolCodigo.PRESENTADOR: {
        "nombre": "Presentador",
        "descripcion": "Presentaciones y exportacion",
        "menus": ("inicio", "presentar", "exportar"),
    },
    RolCodigo.ESPECTADOR: {
        "nombre": "Espectador",
        "descripcion": "Solo lectura",
        "menus": ("inicio",),
    },
    RolCodigo.INTEGRADOR: {
        "nombre": "Integrador",
        "descripcion": "Contratos con otras apps de ZYRA",
        "menus": ("inicio", "red"),
    },
}


def definicion(rol: str) -> dict:
    if rol not in DEFINICIONES:
        raise ValueError("Rol desconocido: " + repr(rol))
    datos = DEFINICIONES[rol]
    return {
        "nombre": datos["nombre"],
        "descripcion": datos["descripcion"],
        "menus": tuple(datos["menus"]),
    }


def menus_de(rol: str) -> tuple:
    return definicion(rol)["menus"]


def roles_oficiales() -> tuple:
    return tuple(DEFINICIONES.keys())
